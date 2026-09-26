"""
================================================================================
MÓDULO: interfaz/rutas/rutas_videos.py
PROYECTO: Ragnarok
DESCRIPCIÓN: Controlador para escaneo de videos en descargas/ y procesados/,
             servicio de streaming MP4 (HTTP 206) y edición en vivo de metadatos.
LÍNEAS: < 180
================================================================================
"""

import json
from flask import Blueprint, request, jsonify, send_from_directory

from interfaz.rutas.compartido import RAIZ, escribir_log

bp_videos = Blueprint("videos", __name__)


@bp_videos.route("/media/descargas/<path:filename>")
def servir_descarga(filename: str):
    """Sirve archivos MP4 y JSON con soporte nativo de HTTP Range (206) para streaming fluido."""
    return send_from_directory(str(RAIZ / "descargas"), filename, conditional=True)


@bp_videos.route("/media/procesados/<path:filename>")
def servir_procesado(filename: str):
    """Sirve archivos MP4 cortados con soporte nativo de HTTP Range (206) para streaming fluido."""
    return send_from_directory(str(RAIZ / "procesados"), filename, conditional=True)


@bp_videos.route("/api/videos", methods=["GET"])
def listar_videos_reales():
    """Escanea descargas/ y procesados/ y construye la lista de videos con sus metadatos."""
    dir_descargas = RAIZ / "descargas"
    dir_procesados = RAIZ / "procesados"
    videos = []

    # 1. Escanear descargas/
    if dir_descargas.exists():
        for carpeta_video in dir_descargas.iterdir():
            if carpeta_video.is_dir():
                archivos = [f for f in carpeta_video.iterdir() if f.is_file() and f.suffix.lower() in ('.mp4', '.webm', '.mkv', '.avi', '.mov')]
                if archivos:
                    ruta_video = archivos[0]
                    ruta_meta = carpeta_video / "metadata.json"
                    meta = {}
                    if ruta_meta.exists():
                        try:
                            with open(ruta_meta, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                        except Exception:
                            pass

                    dur_seg = meta.get("duracion_segundos", 0)
                    tam_bytes = ruta_video.stat().st_size
                    tam_mb = f"{tam_bytes / (1024*1024):.1f} MB" if tam_bytes < 1024*1024*1024 else f"{tam_bytes / (1024*1024*1024):.2f} GB"

                    videos.append({
                        "id": carpeta_video.name,
                        "titulo": meta.get("titulo_original", meta.get("titulo", carpeta_video.name)),
                        "descripcion": meta.get("descripcion_original", meta.get("descripcion", "")),
                        "url_original": meta.get("url_original", ""),
                        "fecha_extraccion": meta.get("fecha_extraccion", ""),
                        "resolucion": meta.get("resolucion", "Auto"),
                        "codec_video": meta.get("codec_video", "h264"),
                        "codec_audio": meta.get("codec_audio", "aac"),
                        "dur": f"{int(dur_seg//60)}:{int(dur_seg%60):02d}" if dur_seg else "Descargado",
                        "durSec": dur_seg,
                        "tamano": tam_mb,
                        "estado": "descargado",
                        "partes": 1,
                        "url_stream": f"/media/descargas/{carpeta_video.name}/{ruta_video.name}",
                    })

    # 2. Escanear procesados/
    if dir_procesados.exists():
        for carpeta_video in dir_procesados.iterdir():
            if carpeta_video.is_dir():
                ruta_meta_seg = carpeta_video / "metadata_segmentada.json"
                clips = list(carpeta_video.glob("*.mp4"))
                if clips:
                    meta = {}
                    if ruta_meta_seg.exists():
                        try:
                            with open(ruta_meta_seg, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                        except Exception:
                            pass

                    dur_seg = meta.get("duracion_original_segundos", 0)
                    tam_total = sum(c.stat().st_size for c in clips)
                    tam_mb = f"{tam_total / (1024*1024):.1f} MB"

                    videos.append({
                        "id": carpeta_video.name,
                        "titulo": meta.get("titulo_original", meta.get("titulo", carpeta_video.name)),
                        "descripcion": meta.get("descripcion_original", meta.get("descripcion", "")),
                        "url_original": meta.get("url_original", ""),
                        "fecha_extraccion": meta.get("fecha_extraccion", ""),
                        "resolucion": meta.get("resolucion", "Auto"),
                        "codec_video": meta.get("codec_video", "h264"),
                        "codec_audio": meta.get("codec_audio", "aac"),
                        "dur": f"{int(dur_seg//60)}:{int(dur_seg%60):02d}" if dur_seg else "Procesado",
                        "durSec": dur_seg,
                        "tamano": tam_mb,
                        "estado": "editado",
                        "partes": len(clips),
                        "url_stream": f"/media/procesados/{carpeta_video.name}/{clips[0].name}",
                    })

    return jsonify({"videos": videos, "total": len(videos)})


@bp_videos.route("/api/videos/<id_video>/metadata", methods=["POST", "PUT"])
def actualizar_metadata_video(id_video: str):
    """Actualiza el título y descripción en los JSONs de metadata en descargas/ y procesados/."""
    data = request.get_json() or {}
    nuevo_titulo = str(data.get("titulo", "")).strip()
    nueva_desc = str(data.get("descripcion", "")).strip()

    if not nuevo_titulo and not nueva_desc:
        return jsonify({"ok": False, "error": "Debe proporcionar título o descripción."}), 400

    actualizado = False
    ruta_meta_descarga = RAIZ / "descargas" / id_video / "metadata.json"
    ruta_meta_procesado = RAIZ / "procesados" / id_video / "metadata_segmentada.json"

    # 1. Actualizar en descargas/
    if ruta_meta_descarga.exists():
        try:
            with open(ruta_meta_descarga, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if nuevo_titulo:
                meta["titulo"] = nuevo_titulo
                meta["titulo_original"] = nuevo_titulo
            if nueva_desc is not None:
                meta["descripcion"] = nueva_desc
                meta["descripcion_original"] = nueva_desc
            with open(ruta_meta_descarga, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            actualizado = True
        except Exception as e:
            return jsonify({"ok": False, "error": f"Error al guardar en descargas: {e}"}), 500

    # 2. Actualizar en procesados/ si existe
    if ruta_meta_procesado.exists():
        try:
            with open(ruta_meta_procesado, "r", encoding="utf-8") as f:
                meta_seg = json.load(f)
            if nuevo_titulo:
                meta_seg["titulo"] = nuevo_titulo
                meta_seg["titulo_original"] = nuevo_titulo
            if nueva_desc is not None:
                meta_seg["descripcion"] = nueva_desc
                meta_seg["descripcion_original"] = nueva_desc
            with open(ruta_meta_procesado, "w", encoding="utf-8") as f:
                json.dump(meta_seg, f, ensure_ascii=False, indent=2)
            actualizado = True
        except Exception:
            pass

    if actualizado:
        resumen_titulo = (nuevo_titulo[:40] + "...") if len(nuevo_titulo) > 40 else nuevo_titulo
        escribir_log("OK", f"Metadatos JSON actualizados para {id_video}: '{resumen_titulo}'")
        return jsonify({"ok": True, "mensaje": "Metadatos actualizados en tiempo real", "id": id_video})
    else:
        return jsonify({"ok": False, "error": f"No se encontró metadata para el ID {id_video}"}), 404
