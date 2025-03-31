# Conversor de Arquivo

## Instalar o FFmpeg

```bash
sudo apt update
sudo apt install ffmpeg
```
## Converter de .dav para .mp4 (sem áudio)

```bash         

ffmpeg -y -i <input.dav> -crf 24 <output.mp4>   
```
## Converter de .dav para .mp4

```bash
ffmpeg -y -i <input.dav> -c:v libx264 -preset slow -crf 24 -c:a aac -b:a 192k <output.mp4>
```
## Converter de .mp4 para .dav

```bash
ffmpeg -y -i <input.mp4> -c:v mpeg2video -q:v 5 -c:a copy <output.dav>
```
## Converter de .mp4 para .avi

```bash                         
    ffmpeg -y -i <input.mp4> -c:v mpeg2video -q:v 5 -c:a copy <output.avi>                              