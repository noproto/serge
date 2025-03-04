from fastapi import APIRouter, HTTPException

from serge.utils.convert import convert_one_file
from serge.utils.migrate import migrate

import huggingface_hub
import os
import urllib.request

from loguru import logger

model_router = APIRouter(
    prefix="/model",
    tags=["model"],
)

models_info = {
    "GPT4AlpacaLoRA-30B": [
        "TheBloke/gpt4-alpaca-lora-30B-4bit-GGML",
        "gpt4-alpaca-lora-30b.ggmlv3.q5_1.bin",
        24.4E9,
        ],
    "AlpacaLoRA-65B": [
        "TheBloke/alpaca-lora-65B-GGML",
        "alpaca-lora-65B.ggmlv3.q5_1.bin",
        48.97E9,
        ],
    "OpenAssistant-30B": [
        "TheBloke/OpenAssistant-SFT-7-Llama-30B-GGML",
        "OpenAssistant-SFT-7-Llama-30B.ggmlv3.q5_1.bin",
        24.4E9,
        ],
    "GPT4All-13B": [
        "TheBloke/GPT4All-13B-snoozy-GGML",
        "GPT4All-13B-snoozy.ggmlv3.q5_1.bin",
        9.76E9,
        ],
    "StableVicuna-13B": [
        "TheBloke/stable-vicuna-13B-GGML",
        "stable-vicuna-13B.ggmlv3.q5_1.bin",
        9.76E9,
        ],
    "Guanaco-7B": [
        "TheBloke/guanaco-7B-GGML",
        "guanaco-7B.ggmlv3.q5_1.bin",
        5.06E9,
        ],
    "Guanaco-13B" : [
        "TheBloke/guanaco-13B-GGML",
        "guanaco-13B.ggmlv3.q5_1.bin",
        9.76E9,
        ],
    "Guanaco-33B" : [
        "TheBloke/guanaco-33B-GGML",
        "guanaco-33B.ggmlv3.q5_1.bin",
        24.4E9,
        ],
    "Guanaco-65B" : [
        "TheBloke/guanaco-65B-GGML",
        "guanaco-65B.ggmlv3.q5_1.bin",
        48.97E9,
        ]

    }

WEIGHTS = "/usr/src/app/weights/"

@model_router.get("/all")
async def list_of_all_models():
    res = []
    installed_models = await list_of_installed_models()
    for model in models_info.keys():
        progress = await download_status(model)
        if f"{model}.bin" in installed_models:
            available = True
            #if model exists in WEIGHTS directory remove it from the list
            installed_models.remove(f"{model}.bin")
        else:
            available = False
        res.append({
            "name": model,
            "size": models_info[model][2],
            "available": available,
            "progress" : progress,
        })
    #append the rest of the models
    for model in installed_models:
        #.bin is removed for compatibility with generate.py
        res.append({
            "name": model.replace(".bin","").lstrip("/"),
            "size": os.stat(WEIGHTS+model).st_size,
            "available": True,
            "progress" : None,
        })
    
    return res

@model_router.get("/downloadable")
async def list_of_downloadable_models():
    files = os.listdir(WEIGHTS)
    files = list(filter(lambda x: x.endswith(".bin"), files))

    installed_models = [i.rstrip(".bin") for i in files]
    
    return list(filter(lambda x: x not in installed_models, models_info.keys()))

@model_router.get("/installed")
async def list_of_installed_models():
    #after iterating through the WEIGHTS directory, return location and filename
    files = [model_location.replace(WEIGHTS,"") +'/'+ bin_file for model_location, directory, filenames in os.walk(WEIGHTS) for bin_file in filenames if os.path.splitext(bin_file)[1] == '.bin']
    files = [i.lstrip("/") for i in files]
    return files 


@model_router.post("/{model_name}/download")
def download_model(model_name: str):
    models = list(models_info.keys())
    if model_name not in models:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if not os.path.exists(WEIGHTS+ "tokenizer.model"):
        print("Downloading tokenizer...")
        url = huggingface_hub.hf_hub_url("nsarrazin/alpaca", "alpaca-7B-ggml/tokenizer.model", repo_type="model", revision="main")
        urllib.request.urlretrieve(url, WEIGHTS+"tokenizer.model")

    
    repo_id, filename,_ = models_info[model_name]

    print(f"Downloading {model_name} model from {repo_id}...")
    url = huggingface_hub.hf_hub_url(repo_id, filename, repo_type="model", revision="main")
    urllib.request.urlretrieve(url, WEIGHTS+f"{model_name}.bin.tmp")

    os.rename(WEIGHTS+f"{model_name}.bin.tmp", WEIGHTS+f"{model_name}.bin")
    convert_one_file(WEIGHTS+ f"{model_name}.bin", WEIGHTS + f"tokenizer.model")
    migrate(WEIGHTS+f"{model_name}.bin")


    return {"message": f"Model {model_name} downloaded"}


@model_router.get("/{model_name}/download/status")
async def download_status(model_name: str):
    models = list(models_info.keys())

    if model_name not in models:
        raise HTTPException(status_code=404, detail="Model not found")

    filesize = models_info[model_name][2]

    bin_path = WEIGHTS+f"{model_name}.bin.tmp"

    if os.path.exists(bin_path):
        currentsize = os.path.getsize(bin_path)
        return min(round(currentsize / filesize*100, 1), 100)        
    return None

@model_router.delete("/{model_name}")
async def delete_model(model_name: str):    
    if model_name+".bin" not in await list_of_installed_models():
        raise HTTPException(status_code=404, detail="Model not found")

    if os.path.exists(WEIGHTS+f"{model_name}.bin"):
        os.remove(WEIGHTS+f"{model_name}.bin")
        return {"message": f"Model {model_name} deleted"}
    
    raise HTTPException(status_code=404, detail="Model file not found")
