#!/usr/bin/env bash
# Encode la séquence PNG du rendu cinématique en MP4 H.264.
# ffmpeg n'est pas présent sur le système : on utilise celui livré avec le paquet
# Python imageio-ffmpeg (installé dans ~/.hermes/venvs/video), qui contient libx264.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRAMES="${ROOT}/chassis/render/frames"
SORTIE="${ROOT}/chassis/render/cinematique.mp4"
PY="${HOME}/.hermes/venvs/video/bin/python"

FF="$("${PY}" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
NB="$(find "${FRAMES}" -name 'f_*.png' | wc -l)"
if [ "${NB}" -eq 0 ]; then
    echo "aucune image dans ${FRAMES} — lance d'abord : blender -b -P chassis/assets/cinematique.py -- cine" >&2
    exit 1
fi
echo "encodage de ${NB} images → ${SORTIE}"

"${FF}" -y -hide_banner -loglevel warning -framerate 30 -i "${FRAMES}/f_%04d.png" \
    -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart \
    "${SORTIE}"

ls -la "${SORTIE}" | awk '{print "MP4 : "$5" octets"}'
"${FF}" -hide_banner -i "${SORTIE}" 2>&1 | grep -E "Duration|Stream #" || true
