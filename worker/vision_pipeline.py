import threading
import time
import cv2
import os

from core.stage_profiler import StageProfiler

"""
Pipeline desacoplado para transmissão e processamento de vídeo em tempo real.

Estrutura de funcionamento:
    [CameraReader]  ---> (CompartimentoUltimoFrame) ---> [Inferência YOLO] ---> [PublicadorDisplay] ---> Fila JPEG
          |                                                                           ^
          +-------------------- (Frame mais recente sem atraso) ----------------------+
"""

class UltimoFrameContainer:
    """
        Guarda exclusivamente o frame mais recente produzido pela câmera.
        Os consumidores são notificados assim que um novo número de sequência é gerado.
    """

    def __init__(self):
        self._condicao = threading.Condition()
        self._dado = None
        self._sequencia = 0

    def salvar(self, dado) -> int:
        """Armazena o novo dado e notifica todas as threads consumidoras."""
        with self._condicao:
            self._dado = dado
            self._sequencia += 1
            self._condicao.notify_all()

            return self._sequencia

    def obter_atual(self):
        """Retorna o dado atual e sua sequência sem bloquear."""
        with self._condicao:
            return self._sequencia, self._dado

    def esperar_novo(self, ultima_seq_lida: int, timeout: float = 0.2):
        """
            Aguarda até que surja um frame com sequência superior à última já lida.
            Retorna (sequencia, dado). Se estourar o timeout, retorna (ultima_sequencia_lida, None).
        """
        with self._condicao:
            if self._sequencia <= ultima_seq_lida:
                self._condicao.wait(timeout)

            if self._sequencia > ultima_seq_lida:
                return self._sequencia, self._dado
            
            return ultima_seq_lida, None


class CacheComTTL:
    """
        Cache simples em memória com tempo de expiração (TTL).
        A função de carregamento é executada fora da trava para não bloquear leituras concorrentes.
    """

    def __init__(self, ttl: float):
        self.tempo_vida = ttl
        self._dados: dict = {}
        self._lock = threading.Lock()

    def obter(self, key, loader):
        agora = time.monotonic()

        with self._lock:
            item = self._dados.get(key)
        
            if item is not None and item[0] > agora:
                return item[1]
        
        # Executa o loader sem segurar o lock
        try:
            valor = loader()
        except Exception:
            # Em caso de falha de conexão, reaproveita o valor antigo se ainda estiver válido
            if item is not None:        # falha no banco: usa o valor antigo em vez de derrubar o loop
                return item[1]
            raise

        with self._lock:
            self._dados[key] = (agora + self.tempo_vida, valor)
        
        return valor

    def invalidar(self, chave=None) -> None:
        with self._lock:
            if chave is None:
                self._dados.clear()
            else:
                self._dados.pop(chave, None)


class LimitadorTempoChave:
    """
        Controla o tempo de intervalo (cooldown) local de eventos em memória,
        substituindo acessos repetitivos ao Redis para checagens simples.
    """

    def __init__(self):
        self._expiracoes: dict = {}
        self._lock = threading.Lock()
        self._ultima_limpeza = time.monotonic()

    def permitir(self, chave, ttl: float) -> bool:
        """Retorna True apenas se o tempo de intervalo da chave tiver expirado."""
        agora = time.monotonic()
        
        with self._lock:
            # Limpeza periódica do dicionário para evitar crescimento indefinido
            if agora - self._ultima_limpeza > 60:
                self._expiracoes = {key: value for key, value in self._expiracoes.items() if value > agora}
                self._ultima_limpeza = agora
            
            if self._expiracoes.get(chave, 0.0) > agora:
                return False
            
            self._expiracoes[chave] = agora + ttl
            
            return True


def aplicar_transformacoes(frame, rotacao, espelhar_h, espelhar_v):
    """
    Aplica rotação ortogonal e espelhamento em matriz de imagem de forma eficiente em memória.
    """
    if frame is None or frame.size == 0:
        return frame

    # Rotação Ortogonal
    if rotacao in (90, -270):
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif rotacao in (180, -180):
        frame = cv2.rotate(frame, cv2.ROTATE_180)
    elif rotacao in (270, -90):
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rotacao not in (0, None):
        h, w = frame.shape[:2]
        centro = (w // 2, h // 2)
        matriz = cv2.getRotationMatrix2D(centro, -rotacao, 1.0)
        frame = cv2.warpAffine(frame, matriz, (w, h))

    # Espelhamento (Flip)
    if espelhar_h and espelhar_v:
        frame = cv2.flip(frame, -1)
    elif espelhar_h:
        frame = cv2.flip(frame, 1)
    elif espelhar_v:
        frame = cv2.flip(frame, 0)

    return frame


def otimizar_config_captura(cap) -> None:
    """
        Ajusta parâmetros do OpenCV VideoCapture para reduzir latência e desbloquear FPS da câmera.
    """
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        backend = (cap.getBackendName() or "").upper()

        if backend == "V4L2":
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(os.getenv("WEBCAM_WIDTH", "1280")))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(os.getenv("WEBCAM_HEIGHT", "720")))
            cap.set(cv2.CAP_PROP_FPS, int(os.getenv("WEBCAM_FPS", "30")))
    
    except Exception:
        pass


class CameraReader(threading.Thread):
    """
        Thread contínua de captura de frames para uma câmera específica.
        Esvazia o buffer interno e deposita apenas o frame mais atual no compartimento compartilhado.
    """

    def __init__(
            self,
            camera_id: int,
            func_abrir_camera,
            func_transformar_frame,
            compartimento: UltimoFrameContainer,
            evento_parada,
            profiler: StageProfiler,
            fps_maximo: float = 0.0,
        ):
        super().__init__(daemon=True, name=f"Thread-Reader-Cam-{camera_id}")
        self.camera_id = camera_id
        self.func_abrir_camera = func_abrir_camera
        self.func_transformar_frame = func_transformar_frame
        self.compartimento = compartimento
        self.evento_parada = evento_parada
        self.profiler = profiler
        self.intervalo_minimo = 1.0 / fps_maximo if fps_maximo > 0 else 0.0
        self.conectado = False
        self.ultimo_frame_timestamp = 0.0

    def run(self):
        cap = None
        proxima_tentativa = 0.0
        ultimo_retrieve = 0.0
        tag_fps = f"cam{self.camera_id}.captura_fps"

        while not self.evento_parada.is_set():
            # Conexão e reconexão automática
            if cap is None or not cap.isOpened():
                self.conectado = False
                
                agora = time.monotonic()
                if agora < proxima_tentativa:
                    time.sleep(0.05)
                    continue
                
                proxima_tentativa = agora + 1.0
                cap = self.func_abrir_camera(self.camera_id)
                
                if cap is None or not cap.isOpened():
                    if cap is not None:
                        cap.release()
                    cap = None
                    time.sleep(0.1)
                    continue
                
                otimizar_config_captura(cap)

            inicio_grab = time.perf_counter()
            if not cap.grab():
                self.conectado = False
                cap.release()
                cap = None
                proxima_tentativa = time.monotonic() + 1.0
                continue
            
            tempo_captura = time.monotonic()

            # Controle de taxa máxima de frames capturados
            if self.intervalo_minimo and (tempo_captura - ultimo_retrieve) < self.intervalo_minimo:
                continue
            
            sucesso, frame = cap.retrieve()
            self.profiler.adicionar_tempo("leitor.grab_retrieve", (time.perf_counter() - inicio_grab) * 1000.0)

            if not sucesso or frame is None or frame.size == 0:
                continue

            ultimo_retrieve = tempo_captura

            # Aplicação das rotações e transformações
            with self.profiler.etapa("leitor.transformacoes"):
                frame = self.func_transformar_frame(frame, self.camera_id)

            self.compartimento.salvar((frame, tempo_captura))
            self.conectado = True
            self.ultimo_frame_timestamp = time.time()
            self.profiler.marcar_evento(tag_fps)

        if cap is not None:
            cap.release()
            print(f"🛑 Thread de captura da câmera {self.camera_id} liberada e finalizada.")


class DisplayPublisher(threading.Thread):
    """
        Thread responsável pela publicação do stream JPEG/MJPEG.
        Renderiza os overlays das detecções sobre o frame mais recente e envia para a fila de visualização.
    """

    TEMPO_TOLERANCIA_ESPECTADOR = 3.0

    def __init__(
            self,
            camera_id: int,
            compartimento: UltimoFrameContainer,
            armazenamento_overlays: dict,
            fila_frames,
            carimbo_espectador,
            evento_parada,
            func_desenhar,
            profiler: StageProfiler,
            fps_alvo: float = 30.0,
            largura_stream: int = 960,
            qualidade_jpeg: int = 75,
    ):
        super().__init__(daemon=True, name=f"Thread-Display-Cam-{camera_id}")
        self.camera_id = camera_id
        self.compartimento = compartimento
        self.armazenamento_overlays = armazenamento_overlays
        self.fila = fila_frames
        self.carimbo_espectador = carimbo_espectador
        self.evento_parada = evento_parada
        self.func_desenhar = func_desenhar
        self.profiler = profiler
        self.intervalo_quadro = 1.0 / fps_alvo if fps_alvo > 0 else 0.0
        self.largura_stream = largura_stream
        self.parametros_jpeg = [int(cv2.IMWRITE_JPEG_QUALITY), int(qualidade_jpeg)]

    def _tem_espectador_ativo(self) -> bool:
        """Verifica se há algum cliente conectado visualizando a rota de vídeo."""
        if self.carimbo_espectador is None:
            return True
        return (time.time() - self.carimbo_espectador.value) < self.TEMPO_TOLERANCIA_ESPECTADOR

    def _publish(self, bytes_jpeg: bytes) -> None:
        """Envia o frame comprimido para a fila, descartando frames acumulados se estiver cheia."""
        if self.fila_frames is None:
            return
        
        try:
            if self.fila_frames.full():
                self.fila_frames.get_nowait()      # descarta o antigo: o espectador sempre vê o mais novo
        except Exception:
            pass

        try:
            self.fila_frames.put(bytes_jpeg, block=False)
        except Exception:
            pass

    def run(self):
        ultima_sequencia = 0
        ultima_publicacao = 0.0
        tag_fps = f"cam{self.camera_id}.display_fps"

        while not self.evento_parada.is_set():
            sequencia, pacote = self.compartimento.esperar_novo(ultima_sequencia, timeout=0.2)
            
            if pacote is None:
                continue
            
            ultima_sequencia = sequencia

            agora = time.monotonic()
            if self.intervalo_quadro and (agora - ultima_publicacao) < self.intervalo_quadro * 0.9:
                continue

            if not self._tem_espectador_ativo():
                continue

            ultima_publicacao = agora
            frame, tempo_captura = pacote
            overlay = self.armazenamento_overlays.get(self.camera_id)
            altura, largura = frame.shape[:2]

            with self.profiler.etapa("display.redimensionamento"):
                if self.largura_stream and largura > self.largura_stream:
                    scale = self.largura_stream / largura
                    img = cv2.resize(frame, (self.largura_stream, int(altura * scale)),
                                     interpolation=cv2.INTER_LINEAR)
                else:
                    escala = 1.0
                    img_final = frame.copy() if overlay else frame   # só copia se for desenhar

            # Desenho dos resultados de detecção e postura
            if overlay:
                with self.profiler.etapa("display.desenho_overlay"):
                    self.func_desenhar(img_final, overlay, escala)

            # Compressão em JPEG
            with self.profiler.etapa("display.compressao_jpeg"):
                sucesso, buffer = cv2.imencode(".jpg", img_final, self.jpeg_params)

            if not sucesso:
                continue

            self._publish(buffer.tobytes())
            self.profiler.adicionar_tempo("e2e.captura_ate_display", (time.monotonic() - tempo_captura) * 1000.0)
            self.profiler.marcar_evento(tag_fps)