# Format iterative plane-peel leaf point clouds + gpt-5-nano caption .txt files
# into MiniGPT-3D / PointLLM-style JSON (caption training, not UPD QA).

import argparse
import json
import os
from pathlib import Path

HUMAN_PROMPT = "What is this?"
DEFAULT_PCL_ROOT = (
    "/project/3dllms/melgin/datasets/CEA/Crops3D_iterative_pcl_plane_peel"
)
DEFAULT_CAPTION_ROOT = (
    "/project/3dllms/melgin/datasets/CEA/Crops3D_iterative_pcl_plane_peel_gpt-5-nano"
)
DEFAULT_PCL_LIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "pcl_lists",
    "Crops3D_train.txt",
)
DATA_REFORMATS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data_reformats",
)
OUTPUT_PREFIX = "overall_Crops3D_iterative_plane_peel_gpt-5-nano"


def default_output_path(pcl_list_path):
    tag = os.path.splitext(os.path.basename(pcl_list_path))[0]
    if tag.startswith("Crops3D_"):
        tag = tag[len("Crops3D_") :]
    return os.path.join(DATA_REFORMATS_DIR, f"{OUTPUT_PREFIX}_{tag}.json")


def load_scene_set(pcl_list_path):
    scenes = set()
    with open(pcl_list_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "@" in line:
                scenes.add(line)
    return scenes


def caption_path_for_ply(ply_rel, caption_root):
    # Cabbage/mvs_1005_01/step01__cluster_00.ply ->
    # .../Cabbage/mvs_1005_01/step01__cluster_00/step01__cluster_00.txt
    rel = Path(ply_rel)
    stem = rel.stem
    return caption_root / rel.parent / stem / f"{stem}.txt"


def build_entry(ply_rel, caption_text, conversation_type="single_round"):
    object_id = str(Path(ply_rel).with_suffix(""))
    return {
        "id": object_id,
        "object_id": object_id,
        "point": ply_rel,
        "rotation": [0, 0, 0],
        "conversation_type": conversation_type,
        "conversations": [
            {"from": "human", "value": HUMAN_PROMPT},
            {"from": "gpt", "value": caption_text},
        ],
    }


def collect_entries(pcl_root, caption_root, scene_set, conversation_type):
    objects = []
    missing_captions = []
    missing_scenes = []

    for scene_key in sorted(scene_set):
        crop, scene = scene_key.split("@", 1)
        scene_dir = pcl_root / crop / scene
        if not scene_dir.is_dir():
            missing_scenes.append(scene_key)
            continue
        for ply_path in sorted(scene_dir.glob("*.ply")):
            ply_rel = str(ply_path.relative_to(pcl_root))
            cap_path = caption_path_for_ply(ply_rel, caption_root)
            if not cap_path.is_file():
                missing_captions.append(ply_rel)
                continue
            caption_text = cap_path.read_text(encoding="utf-8").strip()
            objects.append(build_entry(ply_rel, caption_text, conversation_type))

    return objects, missing_scenes, missing_captions


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Convert iterative plane-peel leaf .ply files and caption .txt files "
            "to MiniGPT-3D training JSON."
        )
    )
    parser.add_argument(
        "--pcl_root",
        default=DEFAULT_PCL_ROOT,
        help="Root directory of iterative plane-peel .ply files",
    )
    parser.add_argument(
        "--caption_root",
        default=DEFAULT_CAPTION_ROOT,
        help="Root directory of gpt-5-nano caption outputs",
    )
    parser.add_argument(
        "--pcl_list",
        default=DEFAULT_PCL_LIST,
        help="Scene list (Crop@mvs_scene per line) for train split filtering",
    )
    parser.add_argument(
        "--output",
        help="Output JSON path (default: derived from pcl_list split name)",
    )
    parser.add_argument(
        "--conversation_type",
        default="single_round",
        help="Conversation type to include in each object",
    )
    args = parser.parse_args()

    pcl_root = Path(args.pcl_root)
    caption_root = Path(args.caption_root)
    output_path = Path(args.output or default_output_path(args.pcl_list))
    scene_set = load_scene_set(args.pcl_list)

    objects, missing_scenes, missing_captions = collect_entries(
        pcl_root, caption_root, scene_set, args.conversation_type
    )

    if missing_scenes:
        raise FileNotFoundError(
            f"{len(missing_scenes)} scenes from pcl_list missing under {pcl_root}: "
            f"{missing_scenes[:5]}"
        )
    if missing_captions:
        raise FileNotFoundError(
            f"{len(missing_captions)} .ply files missing caption .txt: "
            f"{missing_captions[:5]}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(objects, f, indent=2)

    print(f"Scenes in pcl_list: {len(scene_set)}")
    print(f"Entries written: {len(objects)}")
    print(f"Output written to {output_path}")


if __name__ == "__main__":
    main()
