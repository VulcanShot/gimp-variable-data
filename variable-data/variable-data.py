#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import csv
import os
import re
from enum import Enum

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
gi.require_version('Gegl', '0.4')

from gi.repository import Gimp
from gi.repository import GimpUi
from gi.repository import GLib
from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio

plug_in_proc = "vd-variable-data"

class LayerProperty(Enum):
    VISIBILITY = 'visibility'
    FOREGROUND = 'foreground'
    BACKGROUND = 'background'
    TEXT = 'text'
    
def str_to_bool(str):
    match str.lower():
        case 'true': return True
        case 'false': return False
        case _: raise RuntimeError(f"Cannot convert string '{str}' into bool.")
    
def calling_error(procedure, message):
    return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error(f"{plug_in_proc}: {message}"))

def run_dialog(procedure, run_mode, config):
    # TODO: Write a custom dialog
    if run_mode != Gimp.RunMode.INTERACTIVE:
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error("Runmode is not interactive."))
    
    GimpUi.init('python-fu-test-dialog')
    Gegl.init(None)
    dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
    dialog.fill(None)
    if not dialog.run():
        dialog.destroy()
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error("Unable to open dialog window."))
    else:
        dialog.destroy()

def get_layers_by_name(image):
    return { layer.get_name(): layer for layer in image.get_layers() }

def get_paths_by_name(image):
    return { path.get_name(): path for path in image.get_paths() }

def get_top_most_drawable(image):
    for layer in image.get_layers():
        if layer.is_drawable() and not layer.is_text_layer():
            return layer
    return None

def fill_path(image, path, fill_type):
    image.select_item(Gimp.ChannelOps.REPLACE, path)
    Gimp.context_set_opacity(100)
    Gimp.context_set_paint_mode(Gimp.LayerMode.NORMAL_LEGACY)
    get_top_most_drawable(image).edit_fill(fill_type)
    
def fill_item(image, item, color_str, fill_type):
    color = Gegl.Color.new(color_str)
    
    if fill_type == Gimp.FillType.FOREGROUND:
        Gimp.context_set_foreground(color)
    elif fill_type == Gimp.FillType.BACKGROUND:
        Gimp.context_set_background(color)
    else:
        raise RuntimeError('Fill type not supported.')
    
    if item.is_path():
        fill_path(image, item, fill_type)
    else:
        item.edit_fill(fill_type)

# Written by hnbdr / https://gist.github.com/hnbdr/2c28a02d48a9f5c8127a29b8c551aec9
def call_procedure(name, **kwargs):
    procedure = Gimp.get_pdb().lookup_procedure(name)
    if not procedure:
        raise RuntimeError(f"Procedure '{name}' not found")
    
    config = procedure.create_config()
    for key, value in kwargs.items():
        argument = procedure.find_argument(key)
        if not argument:
            raise RuntimeError(f"Argument '{key}' not found in procedure '{name}'")
        
        type_name = argument.value_type.name

        if type_name == 'GimpCoreObjectArray':
            config.set_core_object_array(key, value)
        elif type_name == 'GimpColorArray':
            config.set_color_array(key, value)
        else:
            config.set_property(key, value)
    
    result = procedure.run(config)
    
    # Check if the first value is success
    success = result.index(0)

    if not success:
        raise RuntimeError(f"Procedure '{name}' failed with error: {result.index(1)}")
    
    # Return the result: single value if only one, or an array if more
    if result.length() == 2:
        return result.index(1)  # Only one value, return it directly
    else:
        return [result.index(i) for i in range(1, result.length())]

def variable_data(procedure, run_mode, image, drawables, config, run_data):
    dialog_result = run_dialog(procedure, run_mode, config)
    if dialog_result != None:
        return dialog_result

    csv_filename = config.get_property('csv_filename')
    output_directory = config.get_property('output_directory')
    base_filename = config.get_property('base_filename')
    
    if re.search(r'[<>:/\\|?*\"]|[\0-\31]', base_filename) or re.match(r'^[. ]|.*[. ]$', base_filename):
        return calling_error(procedure, f"Filename '{base_filename}' is invalid.")
    
    if not os.path.isdir(output_directory):
        return calling_error(procedure, f"Directory {output_directory} not found.")

    with open(csv_filename, "r") as csv_file:
        header_row_count = 2
        row_count = sum(1 for _ in csv_file) - header_row_count
        csv_file.seek(0)

        for rindex, row in enumerate(csv.reader(csv_file)):
            if rindex == 0:
                layer_names = row
                continue
            
            if rindex == 1:
                layer_types = row
                continue
            
            rindex = rindex - header_row_count + 1 # Row index in range [0 - row_count]
            duplicate_image = image.duplicate()
            first_drawable = get_top_most_drawable(duplicate_image)
            layers_by_name = get_layers_by_name(duplicate_image)
            paths_by_name = get_paths_by_name(duplicate_image)
            
            if first_drawable == None:
                return calling_error(procedure, "Requieres a layer to work.")

            for cindex, value in enumerate(row):
                layer_name = layer_names[cindex]
                layer_type = layer_types[cindex]
                
                # NOTE: Document that layer take precedence over homonimous paths
                if layer_name in layers_by_name:
                    item = layers_by_name[layer_name]
                elif layer_name in paths_by_name:
                    item = paths_by_name[layer_name]
                else:
                    return calling_error(procedure, f"Layer '{layer_name}' not found.")
                
                match layer_type:
                    case LayerProperty.VISIBILITY.value:
                        try:
                            value = str_to_bool(value)
                        except RuntimeError:
                            return calling_error(procedure, f"Could not convert {value} to bool [{cindex}:{rindex}]")
                        item.set_visible(value)
                    case LayerProperty.FOREGROUND.value:
                        fill_item(duplicate_image, item, value, Gimp.FillType.FOREGROUND)
                    case LayerProperty.BACKGROUND.value:
                        fill_item(duplicate_image, item, value, Gimp.FillType.BACKGROUND)
                    case LayerProperty.TEXT.value:
                        if not item.is_text_layer():
                            return calling_error(procedure, f"Layer is not text [{cindex}:{rindex}]")
                        item.set_text(value)
                    case _:
                        return calling_error(procedure, f"Invalid layer property [{cindex}:{rindex}]")

            filename = base_filename.replace("$n", str(rindex))
            filename = os.path.join(output_directory, filename)
            file = Gio.File.new_for_path(filename)
            Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, duplicate_image, file, options=None)
            Gimp.progress_update((rindex) / float(row_count))
            Gimp.progress_set_text("%s of %s" % (rindex, row_count))
            duplicate_image.delete()
            
        try:
            Gimp.file_show_in_file_manager(file)
        except gi.repository.GLib.GError:
            pass    
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

class VariableData (Gimp.PlugIn):
    def do_query_procedures(self):
        return [ plug_in_proc ]

    def do_set_i18n (self, name):
        return False

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, variable_data, None)

        procedure.set_image_types("*")
        procedure.set_menu_label("Variable data")
        procedure.add_menu_path('<Image>/File/Create/')
        procedure.set_documentation("Illustrator like Variable Data for GIMP",
                                    "Upload a CSV file with columns representing colors. The plugin " + \
                                    "will generate individual pdf files, save each of those in " + \
                                    "specific folder with specific name, then group all those files in new pdf file for printing.",
                                    name)
        procedure.set_attribution("https://github.com/VulcanShot", "https://github.com/VulcanShot", "2025")
        
        procedure.add_file_argument("csv_filename", "Data set (CSV):", "The CSV file with the variable data.",
                                    Gimp.FileChooserAction.OPEN, False, None, GObject.ParamFlags.READWRITE)
        procedure.add_file_argument("output_directory", "Output directory:", "The directory where the output files will be placed.",
                                    Gimp.FileChooserAction.SELECT_FOLDER, False, None, GObject.ParamFlags.READWRITE)
        procedure.add_string_argument("base_filename", "Base filename:",
                                      "The filename of the output files. A $n will be replaced by the index number.",
                                      "output_$n.pdf", GObject.ParamFlags.READWRITE)

        return procedure
    
Gimp.main(VariableData.__gtype__, sys.argv)