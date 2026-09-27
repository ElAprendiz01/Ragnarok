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
import time
from flask import Blueprint, request, jsonify, send_from_directory

from interfaz.rutas.compartido import RAIZ, escribir_log

bp_videos = Blueprint("videos", __name__)
_CACHE_VIDEOS = {"ts": 0, "datos": None}


@bp_videos.route("/media/descargas/<path:filename>")
def servir_descarga(filename: str):
    """Sirve archivos MP4 y JSON con soporte nativo de HTTP Range (206) y cache para streaming fluido."""
    return send_from_directory(str(RAIZ / "descargas"), filename, conditional=True, max_age=86400)


@bp_videos.route("/media/procesados/<path:filename>")
def servir_procesado(filename: str):
    """Sirve archivos MP4 cortados con soporte nativo de HTTP Range (206) y cache para streaming fluido."""
    return send_from_directory(str(RAIZ / "procesados"), filename, conditional=True, max_age=86400)


@bp_videos.route("/api/videos", methods=["GET"])
def listar_videos_reales():
    """Escanea descargas/ y procesados/ y construye la lista de videos con sus metadatos (con caché de 3s)."""
    ahora = time.time()
    if _CACHE_VIDEOS["datos"] is not None and (ahora - _CACHE_VIDEOS["ts"]) < 3.0:
        return jsonify(_CACHE_VIDEOS["datos"])

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

                    # Escanear clips hijos en descargas/<id>/clips/ o procesados/<id>/
                    clips_hijos = []
                    dir_clips_desc = carpeta_video / "clips"
                    if dir_clips_desc.exists():
                        clips_hijos = sorted(dir_clips_desc.glob("*.mp4"))
                    if not clips_hijos and (dir_procesados / carpeta_video.name).exists():
                        clips_hijos = sorted((dir_procesados / carpeta_video.name).glob("*.mp4"))

                    lista_clips = [
                        {
                            "nombre": c.name,
                            "parte": idx,
                            "tamano": f"{c.stat().st_size / (1024*1024):.1f} MB",
                            "url_stream": f"/media/descargas/{carpeta_video.name}/clips/{c.name}" if (dir_clips_desc / c.name).exists() else f"/media/procesados/{carpeta_video.name}/{c.name}"
                        }
                        for idx, c in enumerate(clips_hijos, 1)
                    ]

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
                        "estado": "editado" if lista_clips else "descargado",
                        "partes": len(lista_clips) if lista_clips else 1,
                        "clips": lista_clips,
                        "url_stream": f"/media/descargas/{carpeta_video.name}/{ruta_video.name}",
                    })

    # 2. Escanear procesados/ (videos que solo existan en procesados)
    ids_existentes = {v["id"] for v in videos}
    if dir_procesados.exists():
        for carpeta_video in dir_procesados.iterdir():
            if carpeta_video.is_dir() and carpeta_video.name not in ids_existentes:
                ruta_meta_seg = carpeta_video / "metadata_segmentada.json"
                clips = sorted(carpeta_video.glob("*.mp4"))
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

                    lista_clips_p = [
                        {
                            "nombre": c.name,
                            "parte": idx,
                            "tamano": f"{c.stat().st_size / (1024*1024):.1f} MB",
                            "url_stream": f"/media/procesados/{carpeta_video.name}/{c.name}"
                        }
                        for idx, c in enumerate(clips, 1)
                    ]

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
                        "clips": lista_clips_p,
                        "url_stream": f"/media/procesados/{carpeta_video.name}/{clips[0].name}",
                    })

    resultado = {"videos": videos, "total": len(videos)}
    _CACHE_VIDEOS["ts"] = time.time()
    _CACHE_VIDEOS["datos"] = resultado
    return jsonify(resultado)


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
        _CACHE_VIDEOS["datos"] = None
        resumen_titulo = (nuevo_titulo[:40] + "...") if len(nuevo_titulo) > 40 else nuevo_titulo
        escribir_log("OK", f"Metadatos JSON actualizados para {id_video}: '{resumen_titulo}'")
        return jsonify({"ok": True, "mensaje": "Metadatos actualizados en tiempo real", "id": id_video})
    else:
        return jsonify({"ok": False, "error": f"No se encontró metadata para el ID {id_video}"}), 404


@bp_videos.route("/api/videos/recortar", methods=["POST"])
def recortar_video_endpoint():
    """Recorta un video descargado en partes o clips (TikTok, Shorts, Reels, Secuencia)."""
    data = request.get_json() or {}
    id_video = str(data.get("id_video", "")).strip()
    duracion = data.get("duracion_bloque")
    velocidad = data.get("factor_velocidad")
    purgar = bool(data.get("purgar_original", False))

    if not id_video:
        return jsonify({"ok": False, "error": "Debe proporcionar id_video."}), 400

    dir_video = RAIZ / "descargas" / id_video
    if not dir_video.exists():
        return jsonify({"ok": False, "error": f"No existe la carpeta del video {id_video}"}), 404

    try:
        from fase2_edicion.orquestador_edicion_principal import OrquestadorEdicionPrincipal
        orq = OrquestadorEdicionPrincipal()
        dur_num = float(duracion) if duracion else None
        vel_num = float(velocidad) if velocidad else None
        exito = orq._procesar_video_completo(
            id_video=id_video,
            purgar_original=purgar,
            duracion_bloque=dur_num,
            factor_velocidad=vel_num,
        )
        if not exito:
            return jsonify({"ok": False, "error": "Fallo durante el recorte con FFmpeg."}), 500

        _CACHE_VIDEOS["datos"] = None
        dir_clips = dir_video / "clips"
        clips = sorted(dir_clips.glob("*.mp4")) if dir_clips.exists() else []
        clips_data = [
            {
                "nombre": c.name,
                "parte": idx,
                "tamano": f"{c.stat().st_size / (1024*1024):.1f} MB",
                "url_stream": f"/media/descargas/{id_video}/clips/{c.name}",
            }
            for idx, c in enumerate(clips, 1)
        ]
        escribir_log("OK", f"Video {id_video} segmentado exitosamente en {len(clips_data)} partes.")
        return jsonify({
            "ok": True,
            "id_video": id_video,
            "total_clips": len(clips_data),
            "clips": clips_data,
            "mensaje": f"Video recortado en {len(clips_data)} partes exitosamente.",
        })
    except Exception as e:
        escribir_log("ERROR", f"Excepcion al recortar video {id_video}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_videos.route("/api/videos/<id_video>", methods=["DELETE"])
def eliminar_video_endpoint(id_video: str):
    """Elimina permanentemente de disco el video, sus clips y sus metadatos JSON."""
    id_limpio = str(id_video).strip()
    if not id_limpio or ".." in id_limpio or "/" in id_limpio or "\\" in id_limpio:
        return jsonify({"ok": False, "error": "ID de video no valido."}), 400

    import shutil
    dir_desc = RAIZ / "descargas" / id_limpio
    dir_proc = RAIZ / "procesados" / id_limpio
    eliminado = False

    if dir_desc.exists():
        shutil.rmtree(dir_desc, ignore_errors=True)
        eliminado = True
    if dir_proc.exists():
        shutil.rmtree(dir_proc, ignore_errors=True)
        eliminado = True

    if eliminado:
        _CACHE_VIDEOS["datos"] = None
        escribir_log("WARN", f"Video {id_limpio}, clips y metadata.json eliminados de disco.")
        return jsonify({"ok": True, "id": id_limpio, "mensaje": "Video y metadata JSON eliminados permanentemente."})
    else:
        return jsonify({"ok": False, "error": f"No se encontro el video {id_limpio} en disco."}), 404
