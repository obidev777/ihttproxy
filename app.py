import os
import subprocess
import threading
import time
import signal
import sys
from flask import Flask, request, jsonify

app = Flask(__name__)

# Variable global para el proceso de pproxy
pproxy_process = None

def start_pproxy():
    """Inicia el servidor PProxy en segundo plano"""
    global pproxy_process
    
    try:
        # Configuración de PProxy
        port = os.environ.get('PPROXY_PORT', '8080')
        protocol = os.environ.get('PPROXY_PROTOCOL', 'http')
        auth = os.environ.get('PPROXY_AUTH')  # usuario:contraseña (opcional)
        
        # Construir comando PProxy
        cmd = ['pproxy', '-l', f'{protocol}://0.0.0.0:{port}']
        
        # Agregar autenticación si está configurada
        if auth:
            cmd.extend(['-a', auth])
        
        # Agregar verbose logging
        cmd.append('-v')
        
        print(f"Iniciando PProxy con comando: {' '.join(cmd)}")
        
        # Iniciar proceso
        pproxy_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Hilo para leer logs
        def log_reader():
            while pproxy_process and pproxy_process.poll() is None:
                output = pproxy_process.stdout.readline()
                if output:
                    print(f"[PPROXY] {output.strip()}")
        
        log_thread = threading.Thread(target=log_reader, daemon=True)
        log_thread.start()
        
        print(f"✅ PProxy iniciado en puerto {port} con protocolo {protocol}")
        return True
        
    except Exception as e:
        print(f"❌ Error al iniciar PProxy: {e}")
        return False

def stop_pproxy():
    """Detiene el servidor PProxy"""
    global pproxy_process
    if pproxy_process:
        print("Deteniendo PProxy...")
        pproxy_process.terminate()
        try:
            pproxy_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pproxy_process.kill()
        pproxy_process = None
        print("✅ PProxy detenido")

@app.route('/')
def home():
    """Página de información del proxy"""
    port = os.environ.get('PPROXY_PORT', '8080')
    protocol = os.environ.get('PPROXY_PROTOCOL', 'http')
    auth = os.environ.get('PPROXY_AUTH')
    
    info = {
        'status': 'running',
        'proxy_port': port,
        'protocol': protocol,
        'authentication': 'enabled' if auth else 'disabled',
        'usage': f'Configure su cliente para usar: {protocol}://your-app.railway.app:{port}'
    }
    
    if auth:
        info['auth_credentials'] = auth
    
    return jsonify(info)

@app.route('/health')
def health():
    """Endpoint de salud"""
    global pproxy_process
    if pproxy_process and pproxy_process.poll() is None:
        return jsonify({'status': 'healthy', 'proxy': 'running'})
    else:
        return jsonify({'status': 'unhealthy', 'proxy': 'stopped'}), 503

@app.route('/restart-proxy', methods=['POST'])
def restart_proxy():
    """Reinicia el servidor proxy"""
    stop_pproxy()
    time.sleep(2)
    success = start_pproxy()
    
    if success:
        return jsonify({'status': 'success', 'message': 'Proxy reiniciado'})
    else:
        return jsonify({'status': 'error', 'message': 'Error al reiniciar proxy'}), 500

# Manejo de señales para limpieza
def signal_handler(sig, frame):
    print("Recibida señal de terminación...")
    stop_pproxy()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Iniciar PProxy cuando se inicia la aplicación
@app.before_first_request
def initialize():
    print("🚀 Inicializando aplicación...")
    start_pproxy()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Iniciando servidor web en puerto {port}")
    start_pproxy()  # Iniciar proxy inmediatamente
    app.run(host='0.0.0.0', port=port, debug=False)
