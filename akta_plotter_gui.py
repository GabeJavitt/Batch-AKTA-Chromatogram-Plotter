import sys
import os
import zipfile
import io
import struct
import ctypes  # Needed for Taskbar icon fix
from pathlib import Path
from collections import OrderedDict
from xml.etree import ElementTree
import xmltodict

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                              QFileDialog, QSpinBox, QGroupBox, QMessageBox, 
                              QProgressBar, QTextEdit, QComboBox, QDoubleSpinBox,
                              QListWidget, QAbstractItemView, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- Windows Taskbar Icon Fix ---
try:
    # This identifies the process to Windows so it uses the custom icon in the taskbar
    myappid = 'mycompany.aktaplotter.pro.v2' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# --- Core Data Engine ---

def return_on_failure(errors=(Exception,), default_value=None):
    def decorator(f):
        def applicator(*args, **kwargs):
            try: return f(*args, **kwargs)
            except errors: return default_value
        return applicator
    return decorator

try_except_wrapper = return_on_failure(errors=(Exception,), default_value=None)

class PcUni6(OrderedDict):
    """Parses UNICORN zip files, including nested signal data."""
    _zip_magic_start = b'\x50\x4B\x03\x04\x2D\x00\x00\x00\x08'
    _zip_magic_end = b'\x50\x4B\x05\x06\x00\x00\x00\x00'

    def __init__(self, inp_file):
        super().__init__()
        self.file_name = inp_file
        self._loaded = False

    def load_all_xml(self):
        if not self._loaded: self.load()
        for key in [k for k in self.keys() if (".Xml" in k and "dict" not in k)]:
            self._xml_parse(key)

    def load(self):
        self._loaded = True
        with open(self.file_name, 'rb') as f:
            input_zip = zipfile.ZipFile(f)
            zip_data = {i: input_zip.read(i) for i in input_zip.NameToInfo}
            self.update(zip_data)
            for key, val in zip_data.items():
                tmp_raw = io.BytesIO(val)
                if tmp_raw.read(9) == self._zip_magic_start:
                    proper_zip = tmp_raw.getvalue()
                    f_end = proper_zip.rindex(self._zip_magic_end) + 22
                    tmp_raw = io.BytesIO(proper_zip[0:f_end])
                if zipfile.is_zipfile(tmp_raw):
                    inner = zipfile.ZipFile(tmp_raw)
                    self[key] = {i: inner.read(i) for i in inner.NameToInfo}

        for key in list(self.keys()):
            if "Xml" in key: self[key + "_dict"] = self._unpack_xml(self[key])
            elif isinstance(self[key], dict): self[key] = self._unpack_dict_data(self[key], key)

    @try_except_wrapper
    def _unpack_dict_data(self, data_entry, key):
        for sub_key, sub_value in data_entry.items():
            if "DataType" in sub_key: data_entry[sub_key] = sub_value.decode('utf-8').strip("\r\n")
            elif "True" in key and "Xml" not in key: data_entry[sub_key] = self._unpacker(sub_value)
            else: data_entry[sub_key] = self._unpack_xml(sub_value) if len(sub_value) > 24 else None
        return data_entry

    @staticmethod
    def _unpacker(inp):
        return [x[0] for x in struct.iter_unpack("<f", inp[47:-49])]

    @staticmethod
    @try_except_wrapper
    def _unpack_xml(inp):
        return xmltodict.parse(inp[inp.find(b"<"):].decode())

    def _xml_parse(self, chrom_name):
        chrom_key = chrom_name.replace(".Xml", "")
        self[chrom_key] = {}
        tree = ElementTree.fromstring(self[chrom_name])
        
        me = tree.find('EventCurves')
        if me is not None:
            for i in range(len(me)):
                e_name = me[i].find('Name').text
                if e_name == 'Fraction': e_name = 'Fractions'
                e_data = [(float(e.find('EventVolume').text), e.find('EventText').text) for e in me[i].find('Events')]
                self[chrom_key][e_name] = {'data': e_data, 'type': 'event'}

        mc = tree.find('Curves')
        if mc is not None:
            for i in range(len(mc)):
                d_name, d_fname = mc[i].find('Name').text, mc[i].find('CurvePoints')[0][1].text
                d_unit = mc[i].find('AmplitudeUnit').text
                try:
                    vol, amp = self[d_fname]['CoordinateData.Volumes'], self[d_fname]['CoordinateData.Amplitudes']
                    self[chrom_key][d_name] = {'data': list(zip(vol, amp)), 'unit': d_unit, 'type': 'signal'}
                except: continue

# --- Plotting Engine ---

class ProcessingThread(QThread):
    finished = pyqtSignal()
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    
    def __init__(self, file_list, output_folder, options):
        super().__init__()
        self.file_list, self.output_folder, self.options = file_list, output_folder, options
    
    def run(self):
        out_path = Path(self.output_folder); out_path.mkdir(parents=True, exist_ok=True)
        for idx, f_path in enumerate(self.file_list):
            try:
                reader = PcUni6(str(f_path))
                reader.load(); reader.load_all_xml()
                if 'Chrom.1' in reader:
                    ext = self.options['format']
                    self.plot(reader['Chrom.1'], out_path / f"{Path(f_path).stem}.{ext}", Path(f_path).stem)
                    self.log.emit(f"✓ {Path(f_path).name}")
            except Exception as e: self.log.emit(f"✗ Error {Path(f_path).name}: {str(e)}")
            self.progress.emit(int((idx+1)/len(self.file_list)*100), f"{idx+1}/{len(self.file_list)}")
        self.finished.emit()

    def plot(self, curves, out_path, title):
        fig, ax1 = plt.subplots(figsize=(12, 7))
        xlim, ylim, norm = self.options['xlim'], self.options['ylim'], self.options['normalize']
        
        # Plot Fractions (Filtered)
        secondary = self.options['secondary_curves']
        for key in [k for k in secondary if k in curves and curves[k]['type'] == 'event']:
            for vol, txt in curves[key]['data']:
                if not txt.isdigit(): continue
                if xlim and not (xlim[0] <= vol <= xlim[1]): continue
                ax1.axvline(x=vol, color='grey', linestyle='--', alpha=0.5)
                ax1.text(vol, 0.02, txt, transform=ax1.get_xaxis_transform(), rotation=90, fontsize=8)

        # Plot Curves
        colors = ['tab:blue', 'tab:red', 'tab:green', 'tab:orange', 'tab:purple']
        all_lines = []
        plot_keys = [self.options['primary_curve']] + [k for k in secondary if k in curves and curves[k]['type'] == 'signal']
        
        for i, key in enumerate(plot_keys):
            if key not in curves or not curves[key]['data']: continue
            vol, val = zip(*curves[key]['data'])
            if norm:
                mn, mx = min(val), max(val)
                val = [(v - mn) / (mx - mn) * 100 if mx != mn else 0 for v in val]
                ax, label = ax1, "Relative Intensity (%)"
            else:
                ax = ax1 if i == 0 else ax1.twinx()
                if i > 1: ax.spines['right'].set_position(('outward', 60 * (i-1)))
                label = f"{key} ({curves[key]['unit']})"
            
            line, = ax.plot(vol, val, color=colors[i % 5], label=key, linewidth=1.2)
            all_lines.append(line)
            ax.set_ylabel(label, color=colors[i % 5]); ax.tick_params(axis='y', labelcolor=colors[i % 5])

        ax1.set_xlabel('Volume (mL)'); ax1.set_title(title); ax1.grid(True, alpha=0.3)
        if xlim: ax1.set_xlim(xlim)
        if ylim and not norm: ax1.set_ylim(ylim)
        ax1.legend(all_lines, [l.get_label() for l in all_lines], loc='upper left')
        
        # High-Quality Save
        plt.savefig(out_path, dpi=self.options['dpi'], bbox_inches='tight')
        plt.close()

# --- Graphical User Interface ---

class ChromatogramPlotter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ÄKTA Smart Plotter Pro")
        self.setMinimumSize(850, 750)
        
        # Set Program Icon
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.selected_files = []
        central = QWidget(); self.setCentralWidget(central); layout = QVBoxLayout(central)
        
        # 1. File Selection
        g1 = QGroupBox("1. Manage Data"); layout.addWidget(g1); l1 = QVBoxLayout(g1)
        hb1 = QHBoxLayout(); l1.addLayout(hb1)
        btn_add = QPushButton("Add Files"); btn_add.clicked.connect(self.add_files)
        btn_dir = QPushButton("Add Folder"); btn_dir.clicked.connect(self.add_folder)
        self.btn_scan = QPushButton("Scan for Curves"); self.btn_scan.clicked.connect(self.scan)
        self.btn_scan.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        hb1.addWidget(btn_add); hb1.addWidget(btn_dir); hb1.addWidget(self.btn_scan)
        self.file_label = QLabel("No files selected"); l1.addWidget(self.file_label)

        # 2. Axes Configuration
        g2 = QGroupBox("2. Axis Configuration"); layout.addWidget(g2); l2 = QVBoxLayout(g2)
        self.primary_cb = QComboBox(); l2.addWidget(QLabel("Primary (Left):")); l2.addWidget(self.primary_cb)
        self.secondary_list = QListWidget(); self.secondary_list.setSelectionMode(QAbstractItemView.MultiSelection)
        l2.addWidget(QLabel("Secondary (Right/Events):")); l2.addWidget(self.secondary_list)
        
        # 3. Export & Quality
        g3 = QGroupBox("3. Export Settings"); layout.addWidget(g3); l3 = QVBoxLayout(g3)
        hb3 = QHBoxLayout(); l3.addLayout(hb3)
        self.xmin, self.xmax, self.ymin, self.ymax = QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()
        for s in [self.xmin, self.xmax, self.ymin, self.ymax]: s.setRange(-1000, 9999); hb3.addWidget(s)
        self.xmin.setPrefix("Xmin: "); self.xmax.setPrefix("Xmax: "); self.ymin.setPrefix("Ymin: "); self.ymax.setPrefix("Ymax: ")
        
        hb4 = QHBoxLayout(); l3.addLayout(hb4)
        self.norm_chk = QCheckBox("Normalize (%)"); hb4.addWidget(self.norm_chk)
        self.format_cb = QComboBox(); self.format_cb.addItems(["png", "jpg", "pdf", "svg", "tiff"]); hb4.addWidget(self.format_cb)
        
        # High Quality DPI Setting
        l_dpi = QLabel("Quality (DPI):"); hb4.addWidget(l_dpi)
        self.dpi_sb = QSpinBox(); self.dpi_sb.setRange(72, 1200); self.dpi_sb.setValue(300); hb4.addWidget(self.dpi_sb)
        
        self.out_path = QLineEdit(); b_out = QPushButton("Output Folder"); b_out.clicked.connect(self.set_output)
        hb4.addWidget(self.out_path); hb4.addWidget(b_out)

        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(100); layout.addWidget(self.log)
        self.pbar = QProgressBar(); self.pbar.hide(); layout.addWidget(self.pbar)
        self.run_btn = QPushButton("Generate Plots"); self.run_btn.clicked.connect(self.run_plots)
        self.run_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; height: 40px;")
        layout.addWidget(self.run_btn)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Zip Files", "", "Zip (*.zip)")
        if files: self.selected_files.extend(files); self.file_label.setText(f"{len(self.selected_files)} files loaded.")
    
    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder")
        if d: self.selected_files.extend([str(p) for p in Path(d).glob("*.zip")]); self.file_label.setText(f"{len(self.selected_files)} files loaded.")

    def set_output(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if d: self.out_path.setText(d)

    def scan(self):
        if not self.selected_files: return
        r = PcUni6(self.selected_files[0]); r.load(); r.load_all_xml()
        if 'Chrom.1' in r:
            keys = sorted(r['Chrom.1'].keys())
            self.primary_cb.clear(); self.secondary_list.clear(); self.primary_cb.addItems(keys); self.secondary_list.addItems(keys)

    def run_plots(self):
        if not self.selected_files or not self.out_path.text(): return
        opts = {
            'primary_curve': self.primary_cb.currentText(),
            'secondary_curves': [i.text() for i in self.secondary_list.selectedItems()],
            'xlim': (self.xmin.value(), self.xmax.value()) if self.xmax.value() > 0 else None,
            'ylim': (self.ymin.value(), self.ymax.value()) if self.ymax.value() > 0 else None,
            'normalize': self.norm_chk.isChecked(), 
            'format': self.format_cb.currentText(), 
            'dpi': self.dpi_sb.value()
        }
        self.run_btn.setEnabled(False); self.pbar.show()
        self.t = ProcessingThread(self.selected_files, self.out_path.text(), opts)
        self.t.log.connect(self.log.append); self.t.progress.connect(lambda v, m: self.pbar.setValue(v))
        self.t.finished.connect(lambda: (self.run_btn.setEnabled(True), self.pbar.hide(), QMessageBox.information(self, "Done", "Complete.")))
        self.t.start()

if __name__ == '__main__':
    app = QApplication(sys.argv); app.setStyle('Fusion'); win = ChromatogramPlotter(); win.show(); sys.exit(app.exec_())