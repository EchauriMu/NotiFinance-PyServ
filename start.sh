#!/bin/bash
echo "🚀 Construyendo la imagen Docker..."
docker build -t mi_script .
echo "✅ Imagen creada. Ejecutando contenedor..."
docker run -d --name monitor_nt mi_script
