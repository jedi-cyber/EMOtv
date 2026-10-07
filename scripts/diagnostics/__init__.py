"""Herramientas de diagnóstico local, fuera del producto.

Abren la webcam del equipo del desarrollador con OpenCV y muestran ventanas de
vista previa. La API de EMOtv nunca las importa: en el producto la cámara se
obtiene en el navegador con getUserMedia y los frames llegan por /ws/activity.
No usar con voluntarios ni en el servidor desplegado.
"""
