import sys, os, json, threading, queue, uuid, tempfile, sounddevice as sd, soundfile as sf, numpy as np, requests, pyaudio, wave
from dataclasses import dataclass, asdict
from typing import List, Optional, Any
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

# Frameworks Opcionais
try:
    import yt_dlp as ytdl
except Exception:
    ytdl = None

try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None

try:
    import keyboard
except Exception:
    keyboard = None

APP_DIR = os.path.join(os.path.expanduser('~'), '.py_soundpad')
os.makedirs(APP_DIR, exist_ok=True)
SOUNDS_DB = os.path.join(APP_DIR, 'sounds.json')
DEFAULT_SAMPLE_RATE = 48000

@dataclass
class SoundEntry:
    id: str
    name: str
    path: str
    volume: float = 1.0
    hotkey: Optional[str] = None
    usage_count: int = 0
    created_at: float = QtCore.QDateTime.currentSecsSinceEpoch()


class SoundManager:
    def __init__(self, dbpath=SOUNDS_DB):
        self.dbpath = dbpath
        self.sounds: List[SoundEntry] = []
        self.load()

    def load(self):
        if os.path.exists(self.dbpath):
            try:
                with open(self.dbpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.sounds = [SoundEntry(**s) for s in data]
            except Exception as e:
                print('Failed to load DB:', e)
                self.sounds = []
        else:
            self.sounds = []

    def save(self):
        with open(self.dbpath, 'w', encoding='utf-8') as f:
            json.dump([asdict(s) for s in self.sounds], f, indent=2, ensure_ascii=False)

    def add_sound(self, path, name=None):
        sid = str(uuid.uuid4())
        if not name:
            name = os.path.splitext(os.path.basename(path))[0]
        entry = SoundEntry(id=sid, name=name, path=path)
        self.sounds.append(entry)
        self.save()
        return entry

    def remove(self, sound_id):
        self.sounds = [s for s in self.sounds if s.id != sound_id]
        self.save()

    def rename(self, sound_id, new_name):
        for s in self.sounds:
            if s.id == sound_id:
                s.name = new_name
                break
        self.save()

    def move(self, from_idx, to_idx):
        if 0 <= from_idx < len(self.sounds) and 0 <= to_idx < len(self.sounds):
            s = self.sounds.pop(from_idx)
            self.sounds.insert(to_idx, s)
            self.save()

    def to_list(self):
        return self.sounds


class PlayerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.q = queue.Queue()
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                task = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            fn, args = task
            try:
                fn(*args)
            except Exception as e:
                print('Playback error:', e)

    def enqueue(self, fn, *args):
        self.q.put((fn, args))

    def stop(self):
        self._stop.set()


class SoundPadUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SoundPad - PyQt5')
        self.resize(1000, 640)

        self.manager = SoundManager()
        self.player = PlayerThread()
        self.player.start()

        self.master_volume = 1.0
        self.current_streams: List[Any] = []  # Objetos OutputStream ativos no momento

        # sincronização / sinal de parada
        self.current_streams_lock = threading.Lock()
        self.stop_event = threading.Event()

        self.init_ui()
        self.populate_devices()
        self.refresh_sound_list()

    def init_ui(self):
        w = QtWidgets.QWidget()
        self.setCentralWidget(w)
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Controles superiores
        top = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton('Adicionar som')
        self.add_btn.clicked.connect(self.add_sound)
        top.addWidget(self.add_btn)

        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems(['Tempo: Antigo→Novo','Alfabética', 'Mais usados'])
        self.sort_combo.currentIndexChanged.connect(self.apply_sort)
        top.addWidget(self.sort_combo)

        top.addStretch()

        top.addWidget(QtWidgets.QLabel('Master Volume'))
        self.master_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.master_slider.setRange(0, 100)
        self.master_slider.setValue(100)
        self.master_slider.valueChanged.connect(self.on_master_volume)
        self.master_slider.setFixedWidth(180)
        top.addWidget(self.master_slider)

        self.monitor_checkbox = QtWidgets.QCheckBox('Ativar com Double-Click e Hotkey')
        self.monitor_checkbox.setChecked(True)
        top.addWidget(self.monitor_checkbox)

        layout.addLayout(top)

        # Divisor (painéis arrastáveis)
        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Esquerda: caixa de dispositivos
        dev_box = QtWidgets.QGroupBox('Dispositivos de Saída (marque múltiplos)')
        dev_layout = QtWidgets.QVBoxLayout(dev_box)
        self.devices_list = QtWidgets.QListWidget()
        self.devices_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.devices_list.setMinimumWidth(180)
        dev_layout.addWidget(self.devices_list)
        self.refresh_devices_btn = QtWidgets.QPushButton('Recarregar dispositivos')
        self.refresh_devices_btn.clicked.connect(self.populate_devices)
        dev_layout.addWidget(self.refresh_devices_btn)

        dev_container = QtWidgets.QWidget()
        dc_layout = QtWidgets.QVBoxLayout(dev_container)
        dc_layout.setContentsMargins(0, 0, 0, 0)
        dc_layout.addWidget(dev_box)

        # Centro: lista de sons
        self.sounds_widget = QtWidgets.QListWidget()
        self.sounds_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.sounds_widget.setMinimumWidth(420)
        self.sounds_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        # Direita: controles
        right = QtWidgets.QGroupBox('Controles')
        rlayout = QtWidgets.QVBoxLayout(right)
        rlayout.setContentsMargins(6, 6, 6, 6)

        self.play_btn = QtWidgets.QPushButton('Play')
        self.play_btn.clicked.connect(self.on_play)
        rlayout.addWidget(self.play_btn)

        self.test_btn = QtWidgets.QPushButton('Testar (som local)')
        self.test_btn.clicked.connect(self.on_test)
        rlayout.addWidget(self.test_btn)

        self.stop_btn = QtWidgets.QPushButton('Stop')
        self.stop_btn.clicked.connect(self.on_stop)
        rlayout.addWidget(self.stop_btn)

        self.rename_btn = QtWidgets.QPushButton('Renomear')
        self.rename_btn.clicked.connect(self.on_rename)
        rlayout.addWidget(self.rename_btn)

        self.delete_btn = QtWidgets.QPushButton('Excluir')
        self.delete_btn.clicked.connect(self.on_delete)
        rlayout.addWidget(self.delete_btn)

        rlayout.addWidget(QtWidgets.QLabel('Volume do som'))
        self.volume_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self.on_volume_change)
        rlayout.addWidget(self.volume_slider)

        rlayout.addWidget(QtWidgets.QLabel('Tecla de atalho (ex: ctrl+alt+1)'))
        self.hotkey_edit = QtWidgets.QLineEdit()
        rlayout.addWidget(self.hotkey_edit)
        self.hotkey_set_btn = QtWidgets.QPushButton('Definir atalho')
        self.hotkey_set_btn.clicked.connect(self.on_set_hotkey)
        rlayout.addWidget(self.hotkey_set_btn)

        rlayout.addStretch()
        right_container = QtWidgets.QWidget()
        rc_layout = QtWidgets.QVBoxLayout(right_container)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.addWidget(right)

        # Adicionar widgets ao divisor
        splitter.addWidget(dev_container)
        splitter.addWidget(self.sounds_widget)
        splitter.addWidget(right_container)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([220, 560, 220])
        splitter.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        layout.addWidget(splitter, stretch=1)

        # Status
        self.status = QtWidgets.QLabel('Pronto')
        self.status.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.status.setMinimumHeight(22)
        layout.addWidget(self.status, stretch=0)

        # Conexões de sinais
        self.sounds_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.sounds_widget.itemClicked.connect(self.on_item_clicked)
        self.sounds_widget.itemDoubleClicked.connect(self.on_item_double_clicked)

    # Lista de dispositivos
    def populate_devices(self):
        self.devices_list.clear()
        try:
            devs = sd.query_devices()
            for idx, d in enumerate(devs):
                if isinstance(d, dict) and d.get('max_output_channels', 0) > 0:
                    item = QtWidgets.QListWidgetItem(f"{idx}: {d.get('name', 'Dispositivo')}")
                    item.setData(Qt.ItemDataRole.UserRole, idx)
                    self.devices_list.addItem(item)
                    # Seleciona "cable" automaticamente se disponível
                    if "cable" in d.get('name', '').lower():
                        item.setSelected(True)
                        break
        except Exception as e:
            print("Device query failed:", e)

    # Lista de sons
    def refresh_sound_list(self):
        self.sounds_widget.clear()
        for s in self.manager.to_list():
            it = QtWidgets.QListWidgetItem(f"{s.name}  [{os.path.basename(s.path)}]")
            it.setData(Qt.ItemDataRole.UserRole, s.id)
            self.sounds_widget.addItem(it)

    def apply_sort(self):
        mode = self.sort_combo.currentText()
        if mode == 'Manual':
            pass
        elif mode == 'Alfabética':
            self.manager.sounds.sort(key=lambda x: x.name.lower())
            self.manager.save()
        elif mode == 'Mais usados':
            self.manager.sounds.sort(key=lambda x: -x.usage_count)
            self.manager.save()
        elif mode == 'Tempo: Antigo→Novo':
            self.manager.sounds.sort(key=lambda x: x.created_at)
            self.manager.save()
        self.refresh_sound_list()

    def get_selected_sound(self) -> Optional[SoundEntry]:
        items = self.sounds_widget.selectedItems()
        if not items:
            return None
        sid = items[0].data(Qt.ItemDataRole.UserRole)
        for s in self.manager.sounds:
            if s.id == sid:
                return s
        return None

    def add_sound(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Escolha arquivo', os.path.expanduser('~'))
        if not fn:
            return
        entry = self.manager.add_sound(fn)
        self.refresh_sound_list()
        self.status.setText(f'Adicionado {entry.name}')

    def download_url_to_file(self, url) -> Optional[str]:
        try:
            if 'youtube.com' in url or 'youtu.be' in url:
                if ytdl is None:
                    self.status.setText('yt_dlp não instalado — não é possível baixar YouTube')
                    return None
                tmpdir = tempfile.mkdtemp(dir=APP_DIR)
                ydl_opts: Any = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                }
                with ytdl.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    fn = ydl.prepare_filename(info)
                    if fn.lower().endswith(('.webm', '.m4a', '.mp4')) and AudioSegment is not None:
                        audio = AudioSegment.from_file(fn)
                        out = fn + '.wav'
                        audio.export(out, format='wav')
                        return out
                    return fn
            else:
                r = requests.get(url, stream=True, timeout=30)
                r.raise_for_status()
                ext = os.path.splitext(url)[1] or '.bin'
                fname = os.path.join(APP_DIR, 'downloads', f'{uuid.uuid4()}{ext}')
                os.makedirs(os.path.dirname(fname), exist_ok=True)
                with open(fname, 'wb') as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                return fname
        except Exception as e:
            print('Download error', e)
            return None

    def on_master_volume(self, v):
        # master slider usa 0..100 -> 0.0..1.0
        self.master_volume = v / 100.0

    def on_selection_changed(self):
        s = self.get_selected_sound()
        if not s:
            return
        self.volume_slider.setValue(int(s.volume * 100))
        self.hotkey_edit.setText(s.hotkey or '')

    def on_volume_change(self):
        s = self.get_selected_sound()
        if not s:
            return
        s.volume = self.volume_slider.value() / 100.0
        self.manager.save()

    def on_set_hotkey(self):
        s = self.get_selected_sound()
        if not s:
            return
        hk = self.hotkey_edit.text().strip()
        if not hk:
            s.hotkey = None
            self.manager.save()
            return
        if keyboard is None:
            QtWidgets.QMessageBox.warning(self, 'biblioteca keyboard ausente', 'Instale a biblioteca `keyboard` para usar atalhos (pip install keyboard)')
            return
        if s.hotkey:
            try:
                keyboard.remove_hotkey(s.hotkey)
            except Exception:
                pass
        s.hotkey = hk

        def on_hot():
            # Atalho dispara comportamento de duplo clique (reproduzir em dispositivos selecionados e monitorar se habilitado)
            self.player.enqueue(self.handle_play_for_sound, s)
        try:
            keyboard.add_hotkey(hk, on_hot)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Falha ao definir atalho', f'Não foi possível registrar o atalho: {e}')
            s.hotkey = None
        self.manager.save()

    # Reproduzir, Parar, Testar, Funcionamento do duplo clique

    def get_selected_device_indices(self) -> List[Optional[int]]:
        dev_idxs = [it.data(Qt.ItemDataRole.UserRole) for it in self.devices_list.selectedItems()]
        if not dev_idxs:
            # Retorna saída padrão se nada for selecionado
            try:
                dd = sd.default.device
                if isinstance(dd, (list, tuple)) and len(dd) > 1:
                    return [dd[1]]
            except Exception:
                return [None]
        return dev_idxs

    def handle_play_for_sound(self, s: SoundEntry):
        dev_idxs = self.get_selected_device_indices()
        if self.monitor_checkbox.isChecked():
            has_none = any(d is None for d in dev_idxs)
            if not has_none:
                dev_idxs = list(dev_idxs) + [None]
        # Passamos volume individual; play_to_devices aplicará também self.master_volume
        self.player.enqueue(self.play_to_devices, s.path, s.volume, dev_idxs)
        s.usage_count += 1
        self.manager.save()

    def on_item_clicked(self, item):
        pass

    def on_item_double_clicked(self, item):
        # Duplo clique: reproduzir para microfone (com monitor opcional)
        sid = item.data(Qt.ItemDataRole.UserRole)
        for s in self.manager.sounds:
            if s.id == sid:
                self.handle_play_for_sound(s)
                break

    def on_play(self):
        s = self.get_selected_sound()
        if not s:
            return
        dev_idxs = self.get_selected_device_indices()
        if None not in dev_idxs:
            try:
                dd = sd.default.device
                if isinstance(dd, (list, tuple)) and len(dd) > 1:
                    dev_idxs = list(dev_idxs) + [dd[1]]
                else:
                    dev_idxs = list(dev_idxs) + [None]
            except Exception:
                dev_idxs = list(dev_idxs) + [None]
        self.player.enqueue(self.play_to_devices, s.path, s.volume, dev_idxs)
        s.usage_count += 1
        self.manager.save()

    def on_test(self):
        s = self.get_selected_sound()
        if not s:
            return
        try:
            default_dev = sd.default.device
            dev_idxs = [default_dev[1]] if isinstance(default_dev, (list, tuple)) else [None]
        except:
            dev_idxs = [None]
        self.player.enqueue(self.play_to_devices, s.path, s.volume, dev_idxs)

    def on_stop(self):
        """
        NÃO pare/feche streams aqui. Só sinalize que a reprodução deve parar.
        A própria função play_to_devices (rodando no PlayerThread) vai detectar o evento
        e fechar os streams de maneira segura (na mesma thread que os criou).
        """
        self.stop_event.set()
        # Não chamar st.stop() ou st.close() aqui - evita crash nativo.

    def on_rename(self):
        s = self.get_selected_sound()
        if not s:
            return
        new, ok = QtWidgets.QInputDialog.getText(self, 'Renomear', 'Novo nome:', text=s.name)
        if ok and new:
            self.manager.rename(s.id, new)
            self.refresh_sound_list()

    def on_delete(self):
        s = self.get_selected_sound()
        if not s:
            return
        self.manager.remove(s.id)
        self.refresh_sound_list()

    ##### Núcleo de reprodução com suporte a "m4a" e interrupção #####
    def play_to_devices(self, filepath, volume_individual, device_idxs):
        """
        volume_individual: 0.0..1.0 (o slider do som)
        Aplicamos também self.master_volume (0.0..1.0) ao tocar.
        """

        # limpa pedido anterior de parada
        self.stop_event.clear()

        # Fecha streams antigos (SE existirem) — feito no PlayerThread (seguro)
        with self.current_streams_lock:
            prev_streams = list(self.current_streams)
            self.current_streams = []
        for st in prev_streams:
            try:
                st.stop()
            except Exception:
                pass
            try:
                st.close()
            except Exception:
                pass

        # Lê arquivos (soundfile se possível; fallback para pydub para formatos "m4a/mp3/webm")
        data = None
        sr = None
        try:
            data, sr = sf.read(filepath, dtype='float32')
            # sf.read com dtype='float32' geralmente retorna float32 em -1..1
            if data.ndim == 1:
                data = np.column_stack((data, data))
        except Exception:
            if AudioSegment is None:
                print("Erro: formato não suportado e pydub ausente. Instale pydub e ffmpeg.")
                return
            try:
                audio = AudioSegment.from_file(filepath)
                audio = audio.set_frame_rate(DEFAULT_SAMPLE_RATE).set_channels(2)
                # extrai samples e normaliza para float32 em -1..1
                samples = np.array(audio.get_array_of_samples())
                samples = samples.astype(np.float32)
                # sample_width em bytes (1,2,4). normalizar conforme largura
                if audio.sample_width == 1:
                    # 8-bit unsigned PCM in pydub -> shift to signed
                    samples = (samples - 128.0) / 128.0
                elif audio.sample_width == 2:
                    samples = samples / (2**15)
                elif audio.sample_width == 4:
                    samples = samples / (2**31)
                else:
                    # fallback: tente dividir por 2^(8*sample_width -1)
                    samples = samples / float(2**(8*audio.sample_width - 1))
                channels = audio.channels
                samples = samples.reshape((-1, channels))
                data = samples.astype(np.float32)
                sr = audio.frame_rate
                if data.ndim == 1:
                    data = np.column_stack((data, data))
            except Exception as e:
                print("Erro ao decodificar via pydub:", e)
                return

        # Se nada carregado, aborta
        if data is None or sr is None:
            print('Não foi possível carregar o arquivo:', filepath)
            return

        # Calcula ganho final
        # volume_individual é 0..1 (por som), self.master_volume é 0..1
        gain = float(volume_individual) * float(self.master_volume)

        streams = []
        try:
            for d in device_idxs:
                if d is None:
                    continue
                try:
                    dev_index = int(d)
                except Exception:
                    print(f'[AVISO DISPOSITIVO] Índice de dispositivo inválido: {d}')
                    continue
                try:
                    stream = sd.OutputStream(
                        samplerate=sr,
                        device=dev_index,
                        channels=data.shape[1],
                        dtype='float32',
                        blocksize=2048,
                        latency='high')
                    stream.start()
                    streams.append(stream)
                except Exception as e:
                    print(f'[ERRO DISPOSITIVO] Dispositivo {dev_index} falhou ao abrir: {e}')
                    continue

            if not streams:
                # fallback global (usa sd.play) — aplicamos ganho e clip antes
                if any(d is None for d in device_idxs):
                    try:
                        # aplicar ganho e clip:
                        to_play = data * gain
                        # garantir float32 e no range [-1,1]
                        to_play = np.clip(to_play, -1.0, 1.0).astype(np.float32)
                        sd.play(to_play, sr)
                        sd.wait()
                        return
                    except Exception as e:
                        print('Fallback playback failed:', e)
                        return
                else:
                    print('Nenhum fluxo reproduzível disponível para dispositivos:', device_idxs)
                    return

            # Registra streams de forma segura
            with self.current_streams_lock:
                self.current_streams = streams

            block = 1024
            idx = 0
            n = data.shape[0]
            write_error_printed = False
            while idx < n:
                # Se foi pedido para parar, sai do loop (a finalização fechará os streams)
                if self.stop_event.is_set():
                    break

                to = min(idx + block, n)
                chunk = data[idx:to]

                # garante float32
                if chunk.dtype != np.float32:
                    chunk = chunk.astype(np.float32)

                # aplica ganho e evita clipping
                out_chunk = chunk * gain
                out_chunk = np.clip(out_chunk, -1.0, 1.0).astype(np.float32)

                for st in streams:
                    try:
                        st.write(out_chunk)
                    except Exception as e:
                        if not write_error_printed:
                            print('Stream write error:', e)
                            write_error_printed = True
                        # não abortar todo o processo aqui; continue e feche depois
                idx = to

        except Exception as e:
            print('Playback error', e)
        finally:
            # Fecha streams se ainda estiverem ativos (executado no PlayerThread)
            for st in streams:
                try:
                    st.stop()
                except Exception:
                    pass
                try:
                    st.close()
                except Exception:
                    pass
            with self.current_streams_lock:
                if self.current_streams is streams:
                    self.current_streams = []
            # limpando pedido de parada (pronto para próxima reprodução)
            self.stop_event.clear()

    def play_file(self, filepath, volume):
        try:
            data, sr = sf.read(filepath, dtype='float32')
            if data.ndim == 1:
                data = np.column_stack((data, data))
        except Exception:
            if AudioSegment is None:
                print("Erro: formato não suportado e pydub ausente.")
                return
            try:
                audio = AudioSegment.from_file(filepath)
                audio = audio.set_frame_rate(DEFAULT_SAMPLE_RATE).set_channels(2)
                samples = np.array(audio.get_array_of_samples()).astype(np.float32)
                if audio.sample_width == 1:
                    samples = (samples - 128.0) / 128.0
                elif audio.sample_width == 2:
                    samples = samples / (2**15)
                elif audio.sample_width == 4:
                    samples = samples / (2**31)
                samples = samples.reshape((-1, audio.channels))
                data = samples
                sr = audio.frame_rate
            except Exception as e:
                print("Erro ao decodificar via pydub:", e)
                return

        # aplica volume final com master
        gain = float(volume) * float(self.master_volume)
        to_play = np.clip(data * gain, -1.0, 1.0).astype(np.float32)
        try:
            sd.play(to_play, sr)
            sd.wait()
        except Exception as e:
            print('sd.play failed:', e)

    def closeEvent(self, event):
        # sinaliza parada (play_to_devices fará o fechamento)
        self.stop_event.set()
        # enfileira uma tarefa nula para "acordar" o player thread (opcional)
        try:
            self.player.enqueue(lambda: None)
        except Exception:
            pass
        if keyboard is not None:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        # finalize o player thread
        self.player.stop()
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = SoundPadUI()
    win.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
