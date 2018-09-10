#!/usr/bin/env python

from gimpfu import *
import csv
import os


def get_text_layers(image):
    return {layer.name: layer for layer in image.layers if layer.type == 1}


def get_top_most_drawable(image):
    for layer in image.layers:
        if layer.type == 0:
            return layer


def get_paths(image):
    return {vector.name: vector for vector in image.vectors}


def get_filename_for(row):
    return row[0]


def get_template_variable_for(template_variables, row_index, column_index):
    return template_variables[column_index]


def variable_data(image, csv_filename, pdf_directory, pdf_filename):
    images = [] # saved list of generated images
    template_variables = [] # saved list of generated images

    # for each line in the csv
    with open(csv_filename, "rb") as csv_file:
        row_count = sum(1 for row in csv_file) - 1
        csv_file.seek(0)

        for rindex, row in enumerate(csv.reader(csv_file)):
            if rindex == 0:
                template_variables = row[1:]
                continue

            new_image = image.duplicate()
            filename = get_filename_for(row)
            text_layers = get_text_layers(new_image)
            paths = get_paths(new_image)
            drawable = get_top_most_drawable(new_image)

            # fill-in the template parameters
            for cindex, color in enumerate(row[1:]):
                template_variable = get_template_variable_for(template_variables, rindex, cindex)

                if template_variable in text_layers:
                    text_layer = text_layers[template_variable]
                    gimp.pdb.gimp_text_layer_set_color(text_layer, color)
                elif template_variable in paths:
                    path = paths[template_variable]
                    path.to_selection()
                    gimp.pdb.gimp_image_get_selection(new_image)
                    gimp.pdb.gimp_context_set_background(color)
                    gimp.pdb.gimp_edit_bucket_fill(drawable, 1, 0, 100, 0, 0, 0, 0)

            dirname = os.path.dirname(os.path.abspath(filename))
            if not os.path.isdir(dirname):
                os.makedirs(dirname)

            gimp.pdb.file_pdf_save(new_image, new_image.merge_visible_layers(0), filename, filename, 0, 1, 1)
            images.append(new_image)

            # progress bar
            gimp.pdb.gimp_progress_update( (rindex) / float(row_count))
            gimp.pdb.gimp_progress_set_text("%s of %s" % (rindex, row_count))

        # lastly save the pdf
        pdf_filename = os.path.join(pdf_directory, pdf_filename)
        gimp.pdb.file_pdf_save_multi([image.ID for image in images], len(images), 0, 0, 0, pdf_filename, pdf_filename)


register(
    "joseph_n_m_variable_data",
    "Variable data",
    "Populate an image path and text layers with columns from CSV",
    "Joseph N. M.",
    "Joseph N. M.",
    "2018",
    "Variable Data (CSV)...",
    "*",
    [
        (PF_IMAGE, "image", "", ""),
        (PF_FILENAME, "csv_filename", "Input CSV (*.csv):", ""),
        (PF_DIRNAME, "pdf_directory", "PDF directory:", ""),
        (PF_STRING, "pdf_filename", "PDF file name:", "out.pdf"),
    ],
    [],
    variable_data, menu="<Image>/File/Create")

main()