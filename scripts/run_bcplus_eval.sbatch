#!/bin/bash
#SBATCH --job-name=bcplus_eval_batch
#SBATCH --dependency=singleton
#SBATCH --partition=interactive
#SBATCH --time=240
#SBATCH --account=llmservice_fm_post
#SBATCH --cpus-per-gpu=16
#SBATCH --gpus=4
#SBATCH --output=logs_slurm/%j.out
#SBATCH --error=logs_slurm/%j.err


set -euo pipefail

REPO_ROOT="/lustre/fsw/portfolios/llmservice/users/dongfuj/Workspace/HRCI"
CONTAINER_IMAGE="/lustre/fsw/portfolios/llmservice/users/dongfuj/images/acetoolreason.sqsh"

srun \
  --container-image="${CONTAINER_IMAGE}" \
  --container-mounts="/lustre" \
  --cpus-per-gpu=$SLURM_CPUS_PER_GPU \
  --gpus=$SLURM_GPUS \
  --output=logs_slurm/%x-%j.out \
  --error=logs_slurm/%x-%j.err \
  --export=ALL,PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
  bash -lc "cd ${REPO_ROOT} && source .venv/bin/activate && mkdir -p logs && bash scripts/bcplus_eval/commands.sh"
