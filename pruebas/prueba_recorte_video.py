"""
Prueba unitaria para el modulo de recorte y segmentacion de video.
Verifica que el endpoint /api/videos/recortar funcione correctamente,
preserve el video original intacto y genere la subcarpeta con los clips.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from interfaz.servidor_logs import app
from fase2_edicion.nieto_ejecutor_ffmpeg_optimizado import NietoEjecutorFFmpegOptimizado


class PruebaRecorteVideo(unittest.TestCase):

    def setUp(self):
        self.app_client = app.test_client()
        self.raiz = Path(__file__).parent.parent.resolve()
        self.id_test = "test_clip_unitario"
        self.dir_test = self.raiz / "descargas" / self.id_test
        self.dir_test.mkdir(parents=True, exist_ok=True)

        self.ruta_mp4 = self.dir_test / "video_original.mp4"
        ejecutor = NietoEjecutorFFmpegOptimizado()
        bin_ffmpeg = ejecutor._bin_ffmpeg

        # Generar clip de 4 segundos con FFmpeg con -nostdin para evitar bloqueo
        cmd = [
            bin_ffmpeg, "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=4",
            "-c:v", "libx264", "-preset", "ultrafast",
            str(self.ruta_mp4)
        ]
        subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=15
        )

        meta = {
            "id_video": self.id_test,
            "titulo_original": "Video Test Recorte",
            "descripcion_original": "Probando segmentacion en subcarpeta",
            "duracion_segundos": 4.0
        }
        with open(self.dir_test / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)

    def tearDown(self):
        if self.dir_test.exists():
            shutil.rmtree(self.dir_test, ignore_errors=True)
        dir_proc = self.raiz / "procesados" / self.id_test
        if dir_proc.exists():
            shutil.rmtree(dir_proc, ignore_errors=True)

    def test_recorte_endpoint_y_subcarpeta_clips(self):
        # Recortar en partes de 2 segundos
        resp = self.app_client.post(
            "/api/videos/recortar",
            json={"id_video": self.id_test, "duracion_bloque": 2, "purgar_original": False}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("ok"))
        self.assertGreater(data.get("total_clips"), 0)

        # Video original preservado
        self.assertTrue(self.ruta_mp4.exists(), "El video original no debe eliminarse")

        # Subcarpeta descargas/<id>/clips/ contiene los archivos
        dir_clips = self.dir_test / "clips"
        self.assertTrue(dir_clips.exists(), "Debe existir descargas/<id>/clips")
        clips = list(dir_clips.glob("*.mp4"))
        self.assertGreater(len(clips), 0, "Debe haber clips generados en descargas/<id>/clips")


if __name__ == "__main__":
    unittest.main()
