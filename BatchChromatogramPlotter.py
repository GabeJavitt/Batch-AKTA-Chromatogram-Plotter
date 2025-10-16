import os
import zipfile
import matplotlib.pyplot as plt
import argparse
from typing import Any, Dict, List, Optional
import codecs
import io
import struct
import traceback
from collections import OrderedDict
from xml.etree import ElementTree
from zipfile import ZipFile, is_zipfile
import xmltodict

# --- Start of code integrated from pycorn library ---

def return_on_failure(errors=(Exception,), default_value=None):
    def decorator(f):
        def applicator(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except errors as e:
                print(f'Error {e} on {args, kwargs}')
                traceback.print_exc()
                return default_value
        return applicator
    return decorator

try_except_wrapper = return_on_failure(errors=(Exception,), default_value=None)

class PcUni6(OrderedDict):
    """
    A class for holding the pycorn/RESv6 data, integrated directly into this script.
    A subclass of `dict`, with the form `data_name`: `data`.
    """
    _zip_magic_start = b'\x50\x4B\x03\x04\x2D\x00\x00\x00\x08'
    _zip_magic_end = b'\x50\x4B\x05\x06\x00\x00\x00\x00'
    _sens_data_id = 0
    _sens_data_id2 = 0
    _fractions_id = 0
    _fractions_id2 = 0

    def __init__(self, inp_file):
        OrderedDict.__init__(self)
        self.file_name = inp_file
        self._inject_vol = 0.0
        self._run_name = 'blank'
        self._date = None
        self._loaded = False

    def load_all_xml(self):
        if self._loaded is False:
            self.load(print_log=False)
        xml_keys_to_be_parsed = [key for key in self.keys() if (".Xml" in key and "dict" not in key)]
        for key in xml_keys_to_be_parsed:
            self._xml_parse(key, print_log=False)
        self.clean_up()

    @property
    def date(self):
        if self._date is None:
            root = ElementTree.fromstring(self["Result.xml"])
            date = root.find(".//Created").text
            self._date = date[:10]
        return self._date

    def load(self, print_log=False):
        self._loaded = True
        with open(self.file_name, 'rb') as f:
            input_zip = ZipFile(f)
            zip_data = self._zip2dict(input_zip)
            self.update(zip_data)
            for key in zip_data.keys():
                tmp_raw = io.BytesIO(input_zip.read(key))
                tmp_raw = self._strip_nonstandard_zeros(tmp_raw)
                if not is_zipfile(tmp_raw):
                    continue
                x = {key: self._zip2dict(ZipFile(tmp_raw))}
                self.update(x)

        self_keys = list(self.keys())
        for key in self_keys:
            data_entry = self[key]
            if "Xml" in key:
                self[key + "_dict"] = self._unpack_xml(data_entry, end_index=len(data_entry))
            elif type(data_entry) is dict:
                self[key] = self._unpack_dict_data(data_entry, key)

    def clean_up(self):
        manifest = ElementTree.fromstring(self['Manifest.xml'])
        for i in range(len(manifest)):
            file_name = manifest[i][0].text
            self.pop(file_name)
        self.pop('Manifest.xml')

    @try_except_wrapper
    def _unpack_dict_data(self, data_entry, key):
        for sub_key, sub_value in data_entry.items():
            if "DataType" in sub_key:
                processed_sub_value = sub_value.decode('utf-8').strip("\r\n")
            elif "True" in key and "Xml" not in key:
                processed_sub_value = self._unpacker(sub_value)
            else:
                if len(sub_value) <= 24:
                    processed_sub_value = None
                else:
                    processed_sub_value = self._unpack_xml(sub_value)
            data_entry[sub_key] = processed_sub_value
        return data_entry

    def _strip_nonstandard_zeros(self, tmp_raw):
        f_header = tmp_raw.read(9)
        if f_header == self._zip_magic_start:
            proper_zip = tmp_raw.getvalue()
            f_end = proper_zip.rindex(self._zip_magic_end) + 22
            tmp_raw = io.BytesIO(proper_zip[0:f_end])
        return tmp_raw

    @staticmethod
    def _zip2dict(inp):
        mydict = {}
        for i in inp.NameToInfo:
            tmp_dict = {i: inp.read(i)}
            mydict.update(tmp_dict)
        return mydict

    @staticmethod
    def _unpacker(inp):
        inp_trunc = inp[47:-49]
        values = [x[0] for x in struct.iter_unpack("<f", inp_trunc)]
        return values

    @staticmethod
    @try_except_wrapper
    def _unpack_xml(inp, start_index=None, end_index=None):
        if start_index is None:
            start_index = inp.find(b"<")
        if end_index is None:
            end_index = -1
        input_truncated = inp[start_index:end_index]
        input_decoded = input_truncated.decode()
        xml_dict = xmltodict.parse(input_decoded)
        return xml_dict

    def _xml_parse(self, chrom_name, print_log=False):
        chrom_key = chrom_name.replace(".Xml", "")
        self[chrom_key] = {}
        tree = ElementTree.fromstring(self[chrom_name])
        mc = tree.find('Curves')
        me = tree.find('EventCurves')
        event_dict = {}
        for i in range(len(me)):
            magic_id = self._sens_data_id
            e_name = me[i].find('Name').text
            if e_name == 'Fraction':
                e_name = 'Fractions'
            e_orig = me[i].find('IsOriginalData').text
            e_list = me[i].find('Events')
            e_data = []
            for e in range(len(e_list)):
                e_vol = float(e_list[e].find('EventVolume').text)
                e_txt = e_list[e].find('EventText').text
                e_data.append((e_vol, e_txt))
            if e_orig == "true":
                x = {'run_name': chrom_name, 'data': e_data, 'data_name': e_name, 'magic_id': magic_id}
                event_dict.update({e_name: x})
        self[chrom_key].update(event_dict)
        chrom_dict = {}
        for i in range(len(mc)):
            d_type = mc[i].attrib['CurveDataType']
            d_name = mc[i].find('Name').text
            d_fname = mc[i].find('CurvePoints')[0][1].text
            d_unit = mc[i].find('AmplitudeUnit').text
            magic_id = self._sens_data_id
            try:
                x_dat = self[d_fname]['CoordinateData.Volumes']
                y_dat = self[d_fname]['CoordinateData.Amplitudes']
                zdata = list(zip(x_dat, y_dat))
                if d_name == "UV cell path length":
                    d_name = "xUV cell path length"
                x = {'run_name': chrom_name, 'data': zdata, 'unit': d_unit, 'data_name': d_name, 'data_type': d_type, 'magic_id': magic_id}
                chrom_dict.update({d_name: x})
            except KeyError as e:
                pass # Gracefully skip curves with missing data
        self[chrom_key].update(chrom_dict)

# --- End of code integrated from pycorn library ---


def plot_chromatogram(
    curves_data: Dict[str, Any], 
    output_path: str, 
    zip_filename: str, 
    requested_curves: Optional[List[str]] = None,
    xlim: Optional[List[float]] = None,
    ylim: Optional[List[float]] = None
):
    """
    Generates and saves a plot from a PcUni6 chromatogram data dictionary.
    """
    fig, ax1 = plt.subplots(figsize=(12, 7))
    styles = [
        {'color': 'tab:blue', 'linestyle': '-', 'axis': ax1},
        {'color': 'tab:red', 'linestyle': '--'},
        {'color': 'tab:green', 'linestyle': ':'}
    ]
    active_axes = [ax1]
    all_lines = []
    all_labels = []
    # Separate fraction data from other curves
    fraction_data = curves_data.get('Fractions', {}).get('data')
    print("Available curves in the file:", curves_data.keys())
    curves_to_process = requested_curves
    if not curves_to_process:
        curves_to_process = []
        # Find default curves more robustly
        uv_key = next((key for key in curves_data.keys() if 'UV' in key and isinstance(curves_data[key].get('data'), list)), None)
        cond_key = next((key for key in curves_data.keys() if 'Cond' in key and isinstance(curves_data[key].get('data'), list)), None)
        conc_key = next((key for key in curves_data.keys() if 'Conc' in key and isinstance(curves_data[key].get('data'), list)), None)
        if uv_key: curves_to_process.append(uv_key)
        if cond_key: curves_to_process.append(cond_key)
        if conc_key: curves_to_process.append(conc_key)

    # Filter out 'Fractions' from the main plotting loop if it was requested
    curves_to_plot = [c for c in curves_to_process if c != 'Fractions']

    for i, curve_name in enumerate(curves_to_plot):
        if curve_name not in curves_data or 'data' not in curves_data[curve_name]:
            print(f"Warning: Curve '{curve_name}' not found or has no data in {zip_filename}.")
            continue
        curve_info = curves_data[curve_name]
        volume, values = zip(*curve_info['data'])
        
        if i == 0:
            ax = ax1
            ax.set_xlabel('Volume (mL)')
        else:
            if i >= len(active_axes):
                new_ax = ax1.twinx()
                active_axes.append(new_ax)
            ax = active_axes[i]

        style = styles[i % len(styles)]
        
        if i > 1:
            ax.spines['right'].set_position(('outward', 60 * (i - 1)))

        ax.set_ylabel(f"{curve_name} ({curve_info.get('unit', '')})", color=style['color'])
        ax.plot(volume, values, color=style['color'], linestyle=style['linestyle'], label=curve_name)
        ax.tick_params(axis='y', labelcolor=style['color'])

        lines, labels = ax.get_legend_handles_labels()
        all_lines.extend(lines)
        all_labels.extend(labels)

    if not all_lines:
        print(f"Warning: No valid curves were plotted for {zip_filename}. Skipping file generation.")
        plt.close(fig)
        return
    
    # Plot fractions as vertical lines
    if fraction_data:
        for volume, label in fraction_data:
            ax1.axvline(x=volume, color='grey', linestyle='--', linewidth=0.75)
            ax1.text(volume, 0.02, label, transform=ax1.get_xaxis_transform(), 
                     rotation=90, ha='right', va='bottom', fontsize=8, color='dimgray')
            
    if xlim:
        ax1.set_xlim(xlim)
    if ylim:
        ax1.set_ylim(ylim)

    fig.suptitle(f'Chromatogram for {os.path.splitext(zip_filename)[0]}', fontsize=14)
    ax1.legend(all_lines, [l.get_label() for l in all_lines], loc='upper left')
    
    # Manually adjust subplot parameters to prevent clipping
    fig.subplots_adjust(left=0.1, right=0.85, top=0.9, bottom=0.1)
    
    plt.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"Successfully plotted: {zip_filename} -> {os.path.basename(output_path)}")


def process_zip_file(
    zip_path: str, 
    output_dir: str, 
    requested_curves: Optional[List[str]] = None,
    xlim: Optional[List[float]] = None,
    ylim: Optional[List[float]] = None
):
    """
    Processes a single ÄKTA .zip file to generate a plot.
    """
    zip_filename = os.path.basename(zip_path)
    try:
        unicorn_data = PcUni6(zip_path)
        unicorn_data.load()
        unicorn_data.load_all_xml()

        if 'Chrom.1' in unicorn_data:
            curves = unicorn_data['Chrom.1']
            output_filename = os.path.splitext(zip_filename)[0] + '.png'
            output_path = os.path.join(output_dir, output_filename)
            plot_chromatogram(curves, output_path, zip_filename, requested_curves, xlim, ylim)
        else:
            print(f"Error: Could not find chromatogram data ('Chrom.1') in {zip_filename}. Skipping.")
    except Exception as e:
        print(f"An error occurred while processing {zip_filename}: {e}")


def main():
    """
    Main function to parse arguments and process a directory of ÄKTA .zip files.
    """
    parser = argparse.ArgumentParser(
        description='Batch process ÄKTA .zip result files (including modern UNICORN 6 format) and export plots.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('input_dir', type=str, help='Path to the folder containing your .zip result files.')
    parser.add_argument('output_dir', type=str, help='Path to the folder where plots will be saved.')
    parser.add_argument(
        '--curves',
        nargs='+',
        type=str,
        help='''A list of specific curve names to plot. Use quotes for names with spaces.
If not provided, plots UV, Conductivity, and Gradient by default.

Available curves can include:
- Fractions
- Injection
- "Run Log"
- "UV 1_280"
- "UV 2_295"
- "UV 3_0"
- Cond
- "%% Cond"
- "Conc B"
- "System flow"
- "System linear flow"
- "PreC pressure"
- "DeltaC pressure"
- "Sample flow"
- "Sample linear flow"
- "Sample pressure"
- pH
- "System pressure"
- "PostC pressure"
- "Cond temp"
- "xUV cell path length"
- "Sample flow (CV/h)"
- "System flow (CV/h)"
'''
    )
    parser.add_argument('--xlim', nargs=2, type=float, metavar=('MIN', 'MAX'), help='Set the manual limits for the X-axis (Volume).')
    parser.add_argument('--ylim', nargs=2, type=float, metavar=('MIN', 'MAX'), help='Set the manual limits for the primary Y-axis (the first curve plotted).')
    
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory not found at '{args.input_dir}'")
        return

    if not os.path.exists(args.output_dir):
        print(f"Output directory '{args.output_dir}' not found. Creating it.")
        os.makedirs(args.output_dir)

    print(f"Scanning for .zip files in: {args.input_dir}")
    
    zip_files_found = [f for f in os.listdir(args.input_dir) if f.lower().endswith('.zip')]
    
    if not zip_files_found:
        print("No .zip files found in the input directory.")
        return
        
    print(f"Found {len(zip_files_found)} .zip files to process.")

    for filename in zip_files_found:
        full_path = os.path.join(args.input_dir, filename)
        process_zip_file(full_path, args.output_dir, args.curves, args.xlim, args.ylim)
        
    print("\nBatch processing complete.")

if __name__ == '__main__':
    main()
