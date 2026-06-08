#!/usr/bin/env python
"""
Train a UNet to segment blood vessels from WSI tiles extracted by
extract_annotated_patches.py.

Data layout expected on disk:
    <data_dir>/patches/<slide_name>/tile_NNNN_raw.png
    <data_dir>/masks/<slide_name>/tile_NNNN_mask.png

Patient-level k-fold cross-validation is performed by grouping slides that
belong to the same patient.  The patient ID is parsed from the slide name
using --patient_regex (default: everything before the first underscore).

Example
-------
python train_vessel_unet.py \\
    --data_dir /cluster/projects/kumargroup/ch_fibrosis_analysis/trident \\
    --out_dir  /cluster/projects/kumargroup/ch_fibrosis_analysis/trident/unet_runs \\
    --folds 5 --epochs 50 --batch_size 16
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from sklearn.model_selection import GroupKFold
from PIL import Image
import albumentations as A
from albumentations.pytorch import ToTensorV2
from tqdm import tqdm

try:
    import segmentation_models_pytorch as smp
    _HAS_SMP = True
except ImportError:
    _HAS_SMP = False


# ---------------------------------------------------------------------------
# Minimal UNet fallback (used when smp is unavailable)
# ---------------------------------------------------------------------------

class _DoubleConv(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.net(x)


class _DownBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.conv = _DoubleConv(in_ch, out_ch)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        skip = self.conv(x)
        return self.pool(skip), skip


class _UpBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_ch, out_ch, 2, stride=2)
        self.conv = _DoubleConv(out_ch * 2, out_ch)

    def forward(self, x, skip):
        x = self.up(x)
        # handle odd spatial dimensions
        if x.shape != skip.shape:
            x = F.interpolate(x, size=skip.shape[2:], mode="bilinear", align_corners=False)
        return self.conv(torch.cat([skip, x], dim=1))


class MinimalUNet(nn.Module):
    def __init__(self, in_channels: int = 3, num_classes: int = 1,
                 features: list[int] | None = None):
        super().__init__()
        if features is None:
            features = [64, 128, 256, 512]
        self.downs = nn.ModuleList()
        self.ups = nn.ModuleList()
        ch = in_channels
        for f in features:
            self.downs.append(_DownBlock(ch, f))
            ch = f
        self.bottleneck = _DoubleConv(ch, ch * 2)
        ch = ch * 2
        for f in reversed(features):
            self.ups.append(_UpBlock(ch, f))
            ch = f
        self.head = nn.Conv2d(ch, num_classes, 1)

    def forward(self, x):
        skips = []
        for down in self.downs:
            x, skip = down(x)
            skips.append(skip)
        x = self.bottleneck(x)
        for up, skip in zip(self.ups, reversed(skips)):
            x = up(x, skip)
        return self.head(x)


def build_model(encoder: str, pretrained: bool) -> nn.Module:
    if _HAS_SMP:
        weights = "imagenet" if pretrained else None
        return smp.Unet(
            encoder_name=encoder,
            encoder_weights=weights,
            in_channels=3,
            classes=1,
            activation=None,
        )
    print("[warn] segmentation_models_pytorch not found — using minimal UNet")
    return MinimalUNet()


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def _build_augmentation(train: bool, image_size: int) -> A.Compose:
    if train:
        return A.Compose([
            A.RandomResizedCrop(height=image_size, width=image_size,
                                scale=(0.8, 1.0), ratio=(0.9, 1.1)),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.RandomRotate90(p=0.5),
            A.ColorJitter(brightness=0.2, contrast=0.2,
                          saturation=0.1, hue=0.05, p=0.5),
            A.GaussianBlur(blur_limit=(3, 5), p=0.2),
            A.GaussNoise(p=0.2),
            A.Normalize(mean=(0.485, 0.456, 0.406),
                        std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])
    else:
        return A.Compose([
            A.Resize(height=image_size, width=image_size),
            A.Normalize(mean=(0.485, 0.456, 0.406),
                        std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ])


class VesselTileDataset(Dataset):
    def __init__(
        self,
        tile_pairs: list[tuple[Path, Path]],
        train: bool = True,
        image_size: int = 256,
    ):
        self.pairs = tile_pairs
        self.transform = _build_augmentation(train, image_size)

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, idx: int):
        raw_path, mask_path = self.pairs[idx]
        image = np.array(Image.open(raw_path).convert("RGB"))
        mask = np.array(Image.open(mask_path))

        # Normalise mask to {0, 1} — handles both saved-as-uint8 and
        # saved-as-{0,255} variants
        if mask.max() > 1:
            mask = (mask > 127).astype(np.uint8)
        else:
            mask = mask.astype(np.uint8)

        augmented = self.transform(image=image, mask=mask)
        image_t = augmented["image"].float()
        mask_t = augmented["mask"].float().unsqueeze(0)
        return image_t, mask_t


# ---------------------------------------------------------------------------
# Losses and metrics
# ---------------------------------------------------------------------------

class DiceBCELoss(nn.Module):
    def __init__(self, smooth: float = 1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce = F.binary_cross_entropy_with_logits(logits, targets)
        probs = torch.sigmoid(logits)
        num = (2 * probs * targets).sum(dim=(1, 2, 3)) + self.smooth
        den = (probs + targets).sum(dim=(1, 2, 3)) + self.smooth
        dice_loss = 1.0 - (num / den).mean()
        return bce + dice_loss


def dice_score(probs: torch.Tensor, targets: torch.Tensor,
               threshold: float = 0.5, smooth: float = 1.0) -> float:
    preds = (probs > threshold).float()
    num = (2 * preds * targets).sum() + smooth
    den = preds.sum() + targets.sum() + smooth
    return (num / den).item()


def iou_score(probs: torch.Tensor, targets: torch.Tensor,
              threshold: float = 0.5, smooth: float = 1.0) -> float:
    preds = (probs > threshold).float()
    inter = (preds * targets).sum() + smooth
    union = preds.sum() + targets.sum() - inter + smooth
    return (inter / union).item()


# ---------------------------------------------------------------------------
# Data discovery
# ---------------------------------------------------------------------------

def discover_tiles(data_dir: Path) -> list[tuple[Path, Path, str]]:
    """
    Walk patches/<slide>/ and return (raw_path, mask_path, slide_name) triples.
    Only pairs where both files exist are returned.
    """
    patches_root = data_dir / "patches"
    masks_root = data_dir / "masks"

    if not patches_root.is_dir():
        sys.exit(f"[error] patches directory not found: {patches_root}")
    if not masks_root.is_dir():
        sys.exit(f"[error] masks directory not found: {masks_root}")

    pairs = []
    slide_dirs = sorted(patches_root.iterdir())
    for slide_dir in slide_dirs:
        if not slide_dir.is_dir():
            continue
        slide_name = slide_dir.name
        mask_dir = masks_root / slide_name
        for raw_path in sorted(slide_dir.glob("*_raw.png")):
            stem = raw_path.stem[: -len("_raw")]  # tile_NNNN
            mask_path = mask_dir / f"{stem}_mask.png"
            if mask_path.exists():
                pairs.append((raw_path, mask_path, slide_name))

    return pairs


def patient_id_from_slide(slide_name: str, regex: str) -> str:
    m = re.search(regex, slide_name, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return slide_name


# ---------------------------------------------------------------------------
# Training / evaluation loops
# ---------------------------------------------------------------------------

def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer | None,
    device: torch.device,
    scaler: torch.cuda.amp.GradScaler | None,
) -> dict[str, float]:
    training = optimizer is not None
    model.train() if training else model.eval()

    total_loss = 0.0
    total_dice = 0.0
    total_iou = 0.0
    n_batches = 0

    ctx = torch.enable_grad() if training else torch.no_grad()
    with ctx:
        for images, masks in loader:
            images = images.to(device, non_blocking=True)
            masks = masks.to(device, non_blocking=True)

            if scaler is not None:
                with torch.cuda.amp.autocast():
                    logits = model(images)
                    loss = criterion(logits, masks)
                if training:
                    optimizer.zero_grad()
                    scaler.scale(loss).backward()
                    scaler.step(optimizer)
                    scaler.update()
            else:
                logits = model(images)
                loss = criterion(logits, masks)
                if training:
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()

            probs = torch.sigmoid(logits).detach()
            total_loss += loss.item()
            total_dice += dice_score(probs, masks.detach())
            total_iou += iou_score(probs, masks.detach())
            n_batches += 1

    return {
        "loss": total_loss / max(n_batches, 1),
        "dice": total_dice / max(n_batches, 1),
        "iou": total_iou / max(n_batches, 1),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data_dir", type=Path,
                   default=Path("/cluster/projects/kumargroup/ch_fibrosis_analysis/trident"),
                   help="Root directory containing patches/ and masks/ subdirs.")
    p.add_argument("--out_dir", type=Path,
                   default=Path("/cluster/projects/kumargroup/ch_fibrosis_analysis/trident/unet_runs"),
                   help="Output directory for checkpoints and logs.")
    p.add_argument("--patient_regex", type=str, default=r"^([^_]+)_",
                   help="Regex with one capture group that extracts the patient ID "
                        "from the slide directory name (default: everything before "
                        "the first underscore).  E.g. r'^(P\\d+)' for 'P001_slide1'.")
    p.add_argument("--folds", type=int, default=5,
                   help="Number of cross-validation folds (default: 5).")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch_size", type=int, default=16)
    p.add_argument("--image_size", type=int, default=256,
                   help="Spatial size fed to the network (tiles are resized if needed).")
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--weight_decay", type=float, default=1e-5)
    p.add_argument("--encoder", type=str, default="resnet34",
                   help="smp encoder backbone (ignored when smp is not installed).")
    p.add_argument("--no_pretrain", action="store_true",
                   help="Disable ImageNet pretrained weights.")
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--patience", type=int, default=15,
                   help="Early stopping patience (epochs without val dice improvement).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--amp", action="store_true",
                   help="Use automatic mixed precision (requires CUDA).")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[info] device: {device}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # ---- Discover tiles ------------------------------------------------
    print(f"[info] Scanning {args.data_dir} …")
    all_pairs = discover_tiles(args.data_dir)
    if not all_pairs:
        sys.exit("[error] No tile pairs found. Check data_dir and extraction output.")
    print(f"[info] Found {len(all_pairs):,} tile pairs across "
          f"{len(set(s for _, _, s in all_pairs))} slides")

    raw_paths = [p for p, _, _ in all_pairs]
    mask_paths = [m for _, m, _ in all_pairs]
    slide_names = [s for _, _, s in all_pairs]
    patient_ids = [patient_id_from_slide(s, args.patient_regex) for s in slide_names]

    unique_patients = sorted(set(patient_ids))
    print(f"[info] Unique patients: {len(unique_patients)} — "
          f"{', '.join(unique_patients[:10])}"
          + (" …" if len(unique_patients) > 10 else ""))

    if len(unique_patients) < args.folds:
        print(f"[warn] Fewer patients ({len(unique_patients)}) than folds ({args.folds}). "
              f"Reducing folds to {len(unique_patients)}.")
        args.folds = len(unique_patients)

    # ---- Cross-validation setup ----------------------------------------
    tile_pairs = list(zip(raw_paths, mask_paths))
    groups = np.array(patient_ids)
    indices = np.arange(len(tile_pairs))

    gkf = GroupKFold(n_splits=args.folds)
    splits = list(gkf.split(indices, groups=groups))

    criterion = DiceBCELoss()
    all_fold_results = []

    for fold_idx, (train_idx, val_idx) in enumerate(splits):
        fold = fold_idx + 1
        fold_dir = args.out_dir / f"fold_{fold}"
        fold_dir.mkdir(parents=True, exist_ok=True)

        train_pairs = [tile_pairs[i] for i in train_idx]
        val_pairs = [tile_pairs[i] for i in val_idx]

        val_patients = sorted(set(patient_ids[i] for i in val_idx))
        print(f"\n{'='*60}")
        print(f"Fold {fold}/{args.folds} — val patients: {val_patients}")
        print(f"  train tiles: {len(train_pairs):,}  val tiles: {len(val_pairs):,}")

        train_ds = VesselTileDataset(train_pairs, train=True,
                                     image_size=args.image_size)
        val_ds = VesselTileDataset(val_pairs, train=False,
                                   image_size=args.image_size)

        train_loader = DataLoader(
            train_ds,
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=args.num_workers,
            pin_memory=device.type == "cuda",
            drop_last=True,
        )
        val_loader = DataLoader(
            val_ds,
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=args.num_workers,
            pin_memory=device.type == "cuda",
        )

        model = build_model(args.encoder, pretrained=not args.no_pretrain).to(device)
        optimizer = torch.optim.AdamW(model.parameters(),
                                      lr=args.lr, weight_decay=args.weight_decay)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=args.epochs, eta_min=args.lr * 1e-2
        )
        scaler = torch.cuda.amp.GradScaler() if (args.amp and device.type == "cuda") else None

        best_dice = 0.0
        patience_counter = 0
        fold_log = []

        for epoch in range(1, args.epochs + 1):
            train_metrics = run_epoch(model, train_loader, criterion,
                                      optimizer, device, scaler)
            val_metrics = run_epoch(model, val_loader, criterion,
                                    None, device, None)
            scheduler.step()

            log_row = {
                "epoch": epoch,
                "train_loss": train_metrics["loss"],
                "train_dice": train_metrics["dice"],
                "train_iou": train_metrics["iou"],
                "val_loss": val_metrics["loss"],
                "val_dice": val_metrics["dice"],
                "val_iou": val_metrics["iou"],
            }
            fold_log.append(log_row)

            improved = val_metrics["dice"] > best_dice
            marker = " *" if improved else ""
            print(
                f"  epoch {epoch:3d}/{args.epochs} | "
                f"train loss={train_metrics['loss']:.4f} dice={train_metrics['dice']:.4f} | "
                f"val loss={val_metrics['loss']:.4f} dice={val_metrics['dice']:.4f} "
                f"iou={val_metrics['iou']:.4f}{marker}"
            )

            if improved:
                best_dice = val_metrics["dice"]
                patience_counter = 0
                torch.save(
                    {"epoch": epoch, "model_state": model.state_dict(),
                     "val_dice": best_dice, "val_iou": val_metrics["iou"]},
                    fold_dir / "best_model.pt",
                )
            else:
                patience_counter += 1
                if patience_counter >= args.patience:
                    print(f"  [early stop] no improvement for {args.patience} epochs")
                    break

        # Save per-fold log
        with open(fold_dir / "log.json", "w") as fh:
            json.dump(fold_log, fh, indent=2)

        all_fold_results.append({
            "fold": fold,
            "val_patients": val_patients,
            "best_val_dice": best_dice,
        })
        print(f"  Best val Dice (fold {fold}): {best_dice:.4f}")

    # ---- Summary -------------------------------------------------------
    print(f"\n{'='*60}")
    print("Cross-validation summary:")
    dices = []
    for r in all_fold_results:
        print(f"  Fold {r['fold']}  patients={r['val_patients']}  "
              f"best_dice={r['best_val_dice']:.4f}")
        dices.append(r["best_val_dice"])
    print(f"\n  Mean Dice: {np.mean(dices):.4f} ± {np.std(dices):.4f}")

    summary = {
        "folds": all_fold_results,
        "mean_dice": float(np.mean(dices)),
        "std_dice": float(np.std(dices)),
        "args": {k: str(v) for k, v in vars(args).items()},
    }
    with open(args.out_dir / "cv_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\n  Results saved to {args.out_dir}/cv_summary.json")


if __name__ == "__main__":
    main()
