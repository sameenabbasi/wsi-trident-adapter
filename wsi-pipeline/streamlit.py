import io
import math
import os
import zipfile

from PIL import Image
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")
st.title("📊 Multi-Folder Image Comparison Tool")

MAX_FOLDERS = 6

# Sidebar - Job Directories
st.sidebar.header(f"📁 Select Up to {MAX_FOLDERS} Job Directories")
folders = []

for i in range(MAX_FOLDERS):
    folder_path = st.sidebar.text_input(f"Folder {i + 1} Path")

    if not folder_path:
        break

    if not os.path.isdir(os.path.join(folder_path, "contours")):
        st.sidebar.warning(
            f"`{folder_path}` must contain a 'contours/' folder."
        )
        break

    folders.append(folder_path)

if len(folders) < 2:
    st.info("Please enter at least **2 valid folders** to compare.")
    st.stop()


# Validate Job Directories
all_files = [set(os.listdir(os.path.join(f, "contours"))) for f in folders]
common_files = sorted(list(set.intersection(*all_files)))
if set(common_files) != set(all_files[0]):
    st.warning("Files are not the same in all 'contours/' folders.")
    st.stop()


# Session states
if "image_index" not in st.session_state:
    st.session_state["image_index"] = 0

if "folder_selection_map" not in st.session_state:
    st.session_state["folder_selection_map"] = {}

if "folder_labels" not in st.session_state:
    st.session_state["folder_labels"] = [""] * MAX_FOLDERS


# Image jump dropdown
selected_dropdown_file = st.sidebar.selectbox(
    "🔍 Jump to Image ID", common_files, index=st.session_state["image_index"]
)

if selected_dropdown_file != common_files[st.session_state["image_index"]]:
    st.session_state["image_index"] = common_files.index(selected_dropdown_file)


# Tabs: Comparison View | Summary | Process Lists
tabs = st.tabs(["🖼️ Compare", "📋 Selection Summary", "🧾 Process Lists"])


with tabs[0]:  # Compare tab
    col1, col2, col3 = st.columns([1, 4, 1])
    with col1:
        if st.button("⬅️ Previous") and st.session_state.image_index > 0:
            st.session_state.image_index -= 1
    with col3:
        if (
            st.button("Next ➡️")
            and st.session_state.image_index < len(common_files) - 1
        ):
            st.session_state.image_index += 1

    selected_file = common_files[st.session_state.image_index]
    st.subheader(
        f"🖼️ Comparing: `{selected_file}` ({st.session_state.image_index + 1} of"
        f" {len(common_files)})"
    )

    # Ensure image entry exists
    if selected_file not in st.session_state.folder_selection_map:
        st.session_state.folder_selection_map[selected_file] = -1

    # Toggle button handler
    def on_click(folder_idx):
        if st.session_state.folder_selection_map[selected_file] == folder_idx:
            st.session_state.folder_selection_map[selected_file] = -1
        else:
            st.session_state.folder_selection_map[selected_file] = folder_idx

    # Grid
    num_cols = 3
    num_rows = math.ceil(len(folders) / num_cols)
    for row_idx in range(num_rows):
        cols = st.columns(num_cols)
        for col_idx in range(num_cols):
            idx = row_idx * num_cols + col_idx
            if idx >= len(folders):
                continue

            folder = os.path.join(folders[idx], "contours")
            img_path = os.path.join(folder, selected_file)

            with cols[col_idx]:
                img = Image.open(img_path)

                dimmer = Image.alpha_composite(
                    img.convert("RGBA"),
                    Image.new("RGBA", img.size, (0, 0, 0, 100)),
                ).convert("RGB")

                is_selected = (
                    st.session_state.folder_selection_map[selected_file] == idx
                )

                st.image(
                    [img, dimmer][is_selected],
                    use_container_width=True,
                    caption=f"Folder {idx + 1}",
                )

                st.button(
                    f"Select Folder {idx + 1}",
                    key=f"select_{idx}_{selected_file}",
                    on_click=on_click,
                    args=[idx],
                )

    selected_idx = st.session_state.folder_selection_map[selected_file]
    if selected_idx != -1:
        st.success(
            f"You selected **Folder {selected_idx + 1}** for `{selected_file}`."
        )
    else:
        st.info("No folder selected for this image.")


with tabs[1]:  # Summary tab
    summary_data = []
    for fname in common_files:
        idx = st.session_state.folder_selection_map.get(fname, -1)
        summary_data.append({
            "Image": fname,
            "Selected Folder": f"Folder {idx + 1}" if idx != -1 else "None",
        })

    df = pd.DataFrame(summary_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Export to CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Export Selections to CSV",
        data=csv,
        file_name="selections.csv",
        mime="text/csv",
    )


with tabs[2]:  # Process Lists
    wsi_path = st.text_input(f"WSI Directory")
    if not os.path.exists(wsi_path):
        st.warning("Invalid WSI Directory")
        st.stop()

    wsis = os.listdir(wsi_path)

    # Validate WSI directory
    common_files_set = set([os.path.splitext(f)[0] for f in common_files])
    wsis_set = set([os.path.splitext(f)[0] for f in wsis])

    if not common_files_set.issubset(wsis_set):
        st.warning(
            "Some slide images are missing in WSI directory,"
            f" {sorted(list(common_files_set.difference(wsis_set)))}"
        )
        st.stop()

    st.markdown("### ✏️ Rename Process Lists")
    for i in range(len(folders)):
        st.session_state["folder_labels"][i] = st.text_input(
            f"Rename Process List {i + 1}",
            value=(st.session_state["folder_labels"][i]),
            placeholder=f"folder_{i + 1}",
        )

    # Build dataframes
    img_to_wsis = {}
    for img_fname in common_files:
        for wsi_fname in wsis:
            if os.path.splitext(img_fname)[0] == os.path.splitext(wsi_fname)[0]:
                img_to_wsis[img_fname] = wsi_fname

    summary_data = []
    for fname in common_files:
        wsi = img_to_wsis[fname]

        idx = st.session_state.folder_selection_map.get(fname, -1)
        folder_selected = idx != -1
        folder_renamed = st.session_state["folder_labels"][idx] != ""

        if folder_selected and folder_renamed:
            selected_folder = st.session_state["folder_labels"][idx]
        elif folder_selected:
            selected_folder = f"folder_{idx + 1}"
        else:
            selected_folder = "None"

        summary_data.append({
            "wsi": wsi,
            "Selected Folder": selected_folder,
        })

    df = pd.DataFrame(summary_data)

    # Group by selected folder
    grouped = df[df["Selected Folder"] != "None"].groupby("Selected Folder")
    if not grouped:
        st.info("No selections to preview. You have not selected any folders")

    tab_labels = list(grouped.groups.keys())
    tabs = st.tabs(tab_labels)

    for tab, label in zip(tabs, tab_labels):
        with tab:
            st.dataframe(
                dict(iter(grouped))[label].reset_index()[["wsi"]],
                use_container_width=True,
            )

    # Export to Process Lists
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "x") as zip_file:
        for selected_folder, group_df in grouped:
            csv_bytes = group_df[["wsi"]].to_csv(index=False).encode("utf-8")
            zip_file.writestr(f"{selected_folder}.csv", csv_bytes)

    zip_buffer.seek(0)

    st.download_button(
        label="📦 Export Process Lists to ZIP",
        data=zip_buffer,
        file_name="process_lists.zip",
        mime="application/zip",
    )
