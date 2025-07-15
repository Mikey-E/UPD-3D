import os
import json
import argparse
from torch.utils.data import DataLoader
from pointllm.data import ModelNet
from tqdm import tqdm
import torch
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
from llava.conversation import conv_templates
from llava.model.builder import load_pretrained_model
from llava.mm_utils import tokenizer_image_token, get_model_name_from_path

def existing_dir(path):
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"readable_dir: '{path}' is not a valid directory")
    return path

def existing_file(path):
    if not os.path.isfile(path):
        raise argparse.ArgumentTypeError(f"readable_file: '{path}' is not a valid file")
    return path

class MyClass:
    def __init__(self, args):
        self.vision_tower = None
        self.pretrain_mm_mlp_adapter = args.pretrain_mm_mlp_adapter
        self.encoder_type = 'pc_encoder'
        self.std=args.std
        self.pc_encoder_type = args.pc_encoder_type
        self.pc_feat_dim = 192
        self.embed_dim = 1024
        self.group_size = 64
        self.num_group = 512
        self.pc_encoder_dim = 512
        self.patch_dropout = 0.0
        self.pc_ckpt_path = args.pc_ckpt_path
        self.lora_path = args.lora_path
        self.model_path = args.model_path
        self.get_pc_tokens_way = args.get_pc_tokens_way

def init_model(model_arg_):
    model_path = "llava-vicuna_phi_3_finetune_weight"
    model_name = get_model_name_from_path(model_path)
    model_path = model_arg_.model_path
    tokenizer, model, context_len = load_pretrained_model(model_path, None, model_name)

    if model_arg_.lora_path:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, model_arg_.lora_path)
        print("load lora weight ok")

    model.get_model().initialize_other_modules(model_arg_)
    print("load encoder, mlp ok")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    model.to(dtype=torch.bfloat16)
    model.get_model().vision_tower.to(dtype=torch.float)
    model.to(device)

    return tokenizer, model

def load_point_cloud(ply_file_path):
    """
    Load a point cloud from a PLY file and return it as a tensor.
    Shape is randomly sampled to (8192, 6), where 6 represents (x, y, z, r, g, b)
    """
    import numpy as np
    import torch
    with open(ply_file_path, 'rb') as f:
        # Parse header to get vertex count
        vertex_count = None
        while True:
            line = f.readline().decode('utf-8').strip()
            if line.startswith("element vertex"):
                vertex_count = int(line.split()[-1])
            if line == "end_header":
                break
        if vertex_count is None:
            raise ValueError("PLY header does not contain vertex count")
        # Define numpy dtype for the expected properties
        dtype = np.dtype([
            ('x', 'f8'), ('y', 'f8'), ('z', 'f8'),
            ('nx', 'f8'), ('ny', 'f8'), ('nz', 'f8'),
            ('red', 'u1'), ('green', 'u1'), ('blue', 'u1')
        ])
        data = np.frombuffer(f.read(), dtype=dtype, count=vertex_count)
    # Extract columns: x, y, z, red, green, blue
    pts = np.stack([data['x'], data['y'], data['z'],
                    data['red'], data['green'], data['blue']], axis=1)
    # Randomly sample 8192 points if necessary
    if pts.shape[0] > 8192:
        indices = np.random.choice(pts.shape[0], size=8192, replace=False)
        pts = pts[indices]
    elif pts.shape[0] < 8192:
        # Pad by repeating points
        pad_size = 8192 - pts.shape[0]
        pad_indices = np.random.choice(pts.shape[0], size=pad_size, replace=True)
        pts = np.concatenate([pts, pts[pad_indices]], axis=0)
    return torch.tensor(pts, dtype=torch.float)

def process_samples(model, tokenizer, args, output_file_path):
    results = {}
    #Read the list file and iterate over samples
    with open(args.pcl_list_txt_file_path, 'r') as f:
        lines = f.readlines()
    for line in lines:
        parts = line.strip().split('@')
        if len(parts) < 2:
            raise ValueError(f"Invalid line format: {line}")
        identifier, scene_name = parts[0], parts[1]
        #Build text prompt file path and load text prompt
        txt_path = os.path.join(args.upd_text_folder_path, args.upd_version_name,
                                 args.upd_version_name_subfolder, f"{identifier}@{scene_name}.txt")
        try:
            with open(txt_path, 'r') as tf:
                prompt_text = tf.read().strip()
        except Exception as e:
            print(f"Error reading {txt_path}: {e}")
            continue

        #Build point cloud file path and load point cloud
        pc_path = os.path.join(args.unzipped_point_cloud_path, identifier, scene_name, f"{scene_name}.ply")
        point_cloud = load_point_cloud(pc_path).unsqueeze(0).cuda() #moved to GPU

        #Prepare the prompt: add default image token as prefix as before
        qs = DEFAULT_IMAGE_TOKEN + "\n" + prompt_text

        #Tokenize prompt
        input_ids = tokenizer_image_token(qs, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt").unsqueeze(0).cuda()
        
        #Prepare image tensor
        images_tensor = point_cloud.to(dtype=torch.bfloat16)

        temperature = args.temperature
        top_p = args.top_p
        max_new_tokens = args.max_new_tokens
        min_new_tokens = args.min_new_tokens
        num_beams = args.num_beams

        #Generate output
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=images_tensor,
                do_sample=True if temperature > 0 and num_beams == 1 else False,
                temperature=temperature,
                top_p=top_p,
                num_beams=num_beams,
                max_new_tokens=max_new_tokens,
                min_new_tokens=min_new_tokens,
                use_cache=True,
            )
        answer = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        answer = answer.strip().replace("<|end|>", "").strip()

        scene_key = scene_name.split('.')[0]  # mimic splitting as in minigpt-3d_prog.py
        key = identifier + "@" + scene_key
        results[key] = {"prompt": prompt_text, "response": answer}
        print(f"Processed sample {identifier}.")

    #Save results to a JSON file
    with open(output_file_path, 'w') as fp:
        json.dump(results, fp, indent=2)
    print(f"Saved results to {output_file_path}")
    return results

def main(args):
    #Set output directory
    args.out_path = os.path.join(args.out_path, "evaluation")
    args.output_file_path = os.path.join(args.out_path, "upd_inference_results.json")

    #Create the filename
    os.makedirs(args.out_path, exist_ok=True)
    tag_part = f"{args.json_tag}_" if args.json_tag else ""
    args.pcl_list_txt_filename_noext = os.path.basename(os.path.normpath(args.pcl_list_txt_file_path)).replace('.txt', '')
    output_file_path = os.path.join(args.out_path, f"inf_rslts_gplm_{tag_part}{args.pcl_list_txt_filename_noext}_{args.upd_version_name_subfolder}.json")

    if not os.path.exists(output_file_path):
        # Initialize model and tokenizer using mgpt3d arguments
        model_arg = MyClass(args)
        tokenizer, model = init_model(model_arg)
        model.eval()

        print(f'[INFO] Start processing samples from {args.pcl_list_txt_file_path}.')
        process_samples(model, tokenizer, args, output_file_path)

        #Release model and clear cuda cache
        del model
        torch.cuda.empty_cache()
    else:
        print(f'[INFO] {output_file_path} already exists')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_path", type=str,  default="./output_json")
    parser.add_argument("--pretrain_mm_mlp_adapter", type=str,  required=True)
    parser.add_argument("--lora_path", type=str, default=None)
    parser.add_argument("--model_path", type=str, default='./lava-vicuna_2024_4_Phi-3-mini-4k-instruct')
    parser.add_argument("--std", type=float, default=0.0)
    parser.add_argument("--pc_ckpt_path",  type=str,  required=True, default="./pretrained_weight/Uni3D_PC_encoder/modelzoo/uni3d-small/model.pt")
    parser.add_argument("--pc_encoder_type", type=str, required=True, default='small')
    parser.add_argument("--get_pc_tokens_way", type=str, required=True)
    parser.add_argument("--use_color",  action="store_true", default=True)
    parser.add_argument("--batch_size", type=int, default=10)
    parser.add_argument("--shuffle", type=bool, default=False)
    parser.add_argument("--num_workers", type=int, default=20)

    #evaluation setting
    parser.add_argument("--max_new_tokens", type=int, default=110, help="max number of generated tokens")
    parser.add_argument("--min_new_tokens", type=int, default=0, help="min number of generated tokens")
    parser.add_argument("--num_beams", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--top_k", type=int, default=1)
    parser.add_argument("--top_p", type=float, default=0.7)

    #UPD specific arguments
    parser.add_argument("--upd_text_folder_path", type=existing_dir, required=True, help="Path to the upd_text/ folder.")
    parser.add_argument("--upd_version_name", type=str, required=False, help="Name of the upd version (e.g., 'v1').", default="3D-FRONT")
    parser.add_argument("--upd_version_name_subfolder", type=str, required=True, help="Subfolder name for the upd version (e.g., 'standard').")
    parser.add_argument("--unzipped_point_cloud_path", type=existing_dir, required=True, help="Path to the unzipped point cloud folder containing dirs identifier/scene/scene.ply")
    parser.add_argument("--pcl_list_txt_file_path", type=existing_file, required=True, help="Path to the text file containing point cloud identifiers and scene names.")
    parser.add_argument("--json_tag", type=str, required=False, help="Optional tag to include in the output JSON filename, eg 'ft-comb' for finetune-combined", default=None)

    args = parser.parse_args()
    main(args)