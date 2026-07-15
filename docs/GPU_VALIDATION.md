# GPU image validation (twhyne/twhyne:gpu)

CI proves the CUDA image boots and answers in CPU-fallback mode (GitHub
runners have no GPU). GPU offload itself must be validated on real NVIDIA
hardware before the GPU tier is announced or documented to users. No
physical GPU is needed on our side: rent one for ~15 minutes.

## Rented-GPU validation (~$0.30, ~20 minutes)

1. Rent a machine: RunPod / Lambda / vast.ai, any NVIDIA T4/A4000/3090+
   instance with a Docker template (choose "RunPod PyTorch" or any
   CUDA 12.x image with docker available, or use their "Deploy Docker
   image" flow directly with `twhyne/twhyne:gpu`).
2. On the box:
   ```bash
   nvidia-smi                        # GPU visible?
   docker run --rm --gpus all --entrypoint python3 twhyne/twhyne:gpu -c \
     "from llama_cpp import llama_supports_gpu_offload; \
      print('gpu offload supported:', llama_supports_gpu_offload())"
   ```
   Must print `True`.
3. Real inference on the GPU (downloads a small model, watches offload):
   ```bash
   mkdir -p /tmp/models
   curl -Ls -o /tmp/models/qwen0.5.gguf \
     https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
   docker run --rm --gpus all -v /tmp/models:/m --entrypoint python3 twhyne/twhyne:gpu -c "
   import time
   from llama_cpp import Llama
   m = Llama(model_path='/m/qwen0.5.gguf', n_gpu_layers=-1, verbose=True)
   t0=time.time(); r = m('Q: What is 2+2? A:', max_tokens=64)
   dt=time.time()-t0; toks=r['usage']['completion_tokens']
   print(f'{toks} tokens in {dt:.1f}s = {toks/dt:.0f} tok/s')"
   ```
   Success = the verbose log shows layers `offloaded to GPU` and tok/s
   is dramatically above CPU (hundreds, for a 0.5B).
4. Full app boot with a 7B (optional but recommended): run the normal
   entrypoint with `--gpus all`, the models volume, and a license key;
   ask a code question; confirm the launcher-window log line
   `Code generation: ... tok/s` reports 40+ tok/s.

## Sign-off

Record in the release notes: GPU model, driver version, tok/s observed.
Until a sign-off exists, the :gpu tag is EXPERIMENTAL - do not link it
from the site or launchers.
