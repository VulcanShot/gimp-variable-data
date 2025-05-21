#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import csv
import os

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

def run_dialog(procedure, run_mode, config):
    # TODO: Write a custom dialog
    if run_mode != Gimp.RunMode.INTERACTIVE:
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
    
    GimpUi.init('python-fu-test-dialog')
    Gegl.init(None)
    dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
    dialog.fill(None)
    if not dialog.run():
        dialog.destroy()
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
    else:
        dialog.destroy()

def get_text_layers_by_name(image):
    return { layer.get_name(): layer for layer in image.get_layers() if layer.is_text_layer() }

def get_paths_by_name(image):
    return { path.get_name(): path for path in image.get_paths() }

def get_top_most_drawable(image):
    for layer in image.get_layers():
        if layer.is_drawable() and not layer.is_text_layer():
            return layer
    return None

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
    pdf_directory = config.get_property('pdf_directory')
    pdf_filename = config.get_property('pdf_filename')
    
    new_image = image.duplicate()
    drawable = get_top_most_drawable(new_image)
    text_layers_by_name = get_text_layers_by_name(new_image)
    paths_by_name = get_paths_by_name(new_image)
    
    if drawable == None:
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, 
                                           GLib.Error(f"Procedure '{plug_in_proc}' requieres a layer to work."))

    images = [] # saved list of generated images

    # for each line in the csv
    with open(csv_filename, "r") as csv_file:
        row_count = sum(1 for row in csv_file) - 1
        csv_file.seek(0)

        for rindex, row in enumerate(csv.reader(csv_file), 0):
            if rindex == 0:
                layer_names = row
                continue
            
            filename = row[0]

            # fill-in the template parameters
            for cindex, value in enumerate(row[1:], 1):
                layer_name = layer_names[cindex]
                color = Gegl.Color.new(value)

                if layer_name in text_layers_by_name:
                    text_layers_by_name[layer_name].set_color(color)
                elif layer_name in paths_by_name:
                    new_image.select_item(Gimp.ChannelOps.REPLACE, paths_by_name[layer_name])
                    Gimp.context_set_opacity(100)
                    Gimp.context_set_paint_mode(Gimp.LayerMode.NORMAL_LEGACY)
                    Gimp.context_set_background(color)
                    drawable.edit_fill(Gimp.FillType.BACKGROUND)
                else:
                    return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, 
                                           GLib.Error(f"Layer '{layer_name}' not found."))

            dirname = os.path.dirname(os.path.abspath(filename))
            if not os.path.isdir(dirname):
                os.makedirs(dirname)

            call_procedure('file-pdf-export', image=new_image, file=Gio.File.new_for_path(filename), options=None)
            images.append(new_image)
            Gimp.progress_update((rindex) / float(row_count))
            Gimp.progress_set_text("%s of %s" % (rindex, row_count))

        # lastly save the pdf
        pdf_filename = "file://" + os.path.join(pdf_directory, pdf_filename)
        # FIXME: uri parameter is ignored, a dialog is shown to ask the user to configure the export
        call_procedure("file-pdf-export-multi", images=images, uri=pdf_filename)
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
        procedure.set_attribution("Joseph N. M.", "Joseph N. M.", "2018")
        
        procedure.add_file_argument("csv_filename", "CSV File", None, Gimp.FileChooserAction.OPEN, False, None, # FileChooserAction.ANY (?
                                    GObject.ParamFlags.READWRITE)
        procedure.add_file_argument("pdf_directory", "PDF Directory", None, Gimp.FileChooserAction.SELECT_FOLDER, False, None,
                                    GObject.ParamFlags.READWRITE)
        procedure.add_string_argument("pdf_filename", "PDF File", None, "out.pdf", GObject.ParamFlags.READWRITE)

        return procedure
    
Gimp.main(VariableData.__gtype__, sys.argv)