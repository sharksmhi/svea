import codecs
import shutil
import time
from pathlib import Path
import os
import openpyxl

from ctdpy.core import session as ctdpy_session
from ctdpy.core.utils import generate_filepaths

from svea import exceptions

import logging
import logging.config
import logging.handlers


class SveaSteps:
    def __init__(self):
        self.sbe_processing = False
        self.create_metadata_file = False
        self.create_standard_format = False
        self.perform_automatic_qc = False
        self.open_visual_qc = False
        self.send_files_to_ftp = False
        self.import_to_lims = False
        self.create_station_plots = False


class SveaController:
    def __init__(self, logger=None):
        self.logger = get_logger(logger)

        self._working_directory = None
        self._export_directory = None

        self._steps = SveaSteps()

        self._metadata_object = Metadata(logger=self.logger)

        self._sensorinfo_object = SensorInfo(logger=self.logger)

        self._metadata_file_object = MetadataFile(logger=self.logger)
        self._metadata_file_object.metadata_object = self._metadata_object
        self._metadata_file_object.sensor_info_object = self._sensorinfo_object

        self._cnv_files_object = CNVfiles(logger=self.logger)

        self._create_metadata_file_object = CreateMetadataFile(logger=self.logger)
        self._create_metadata_file_object.metadata_file_object = self._metadata_file_object
        self._create_metadata_file_object.cnv_files_object = self._cnv_files_object

        self._create_standard_format_files_object = CreateStandardFormatFiles(logger=self.logger)
        self._create_standard_format_files_object.metadata_file_object = self._metadata_file_object
        self._create_standard_format_files_object.cnv_files_object = self._cnv_files_object

        self.logger.info('SveaController instance created!')

    def _assert_directory(self):
        if not self._working_directory:
            text = 'Working directory is not set'
            self.logger.error(text)
            raise exceptions.MissingFiles(text)
        elif not self._working_directory.exists():
            os.makedirs(self._working_directory)
            self.logger.info(f'Woring directory created: {self._working_directory}')

    @property
    def working_directory(self):
        return self._working_directory

    @working_directory.setter
    def working_directory(self, directory):
        self._working_directory = Path(directory)
        self._export_directory = Path(self._working_directory, 'export')
        self._metadata_file_object.file_path = self._working_directory
        self._create_standard_format_files_object.directory = self._export_directory
        self.logger.info(f'Working directory set to: {directory}')

    @property
    def metadata_file_path(self):
        return self._metadata_file_object.file_path

    def sbe_processing(self, file_paths='temp list with cnv files'):
        # TODO: run processing
        self._cnv_files_object.file_paths = file_paths
        self._steps.sbe_processing = True

    def create_metadata_file(self):
        self._assert_directory()
        self._create_metadata_file_object.create_file()
        self._cnv_files_object.change_location(self._working_directory)
        self._steps.create_metadata_file = True

    def create_standard_format(self):
        self._assert_directory()
        self._create_standard_format_files_object.create_files()
        self._steps.create_standard_format = True

    def perform_automatic_qc(self):
        self._steps.perform_automatic_qc = True

    def open_visual_qc(self):
        self._steps.open_visual_qc = True

    def send_files_to_ftp(self):
        self._steps.send_files_to_ftp = True

    def import_to_lims(self):
        self._steps.import_to_lims = True

    def create_station_plots(self):
        self._steps.create_station_plots = True

    @property
    def metadata(self):
        return self._metadata_object.get()

    @metadata.setter
    def metadata(self, metadata):
        self._metadata_object.set(metadata)  # option to update as well (other method)

    @property
    def cnv_files(self):
        return self._cnv_files_object.file_paths

    @cnv_files.setter
    def cnv_files(self, paths):
        self._cnv_files_object.file_paths = paths

    def set_overwrite_permission(self, overwrite):
        if type(overwrite) != bool:
            text = 'Overwrite permission needs to be of type boolean'
            self.logger.error(text)
            raise exceptions.DtypeError(text)
        self._metadata_file_object.allow_overwrite = overwrite
        self._cnv_files_object.allow_overwrite = overwrite
        self._create_metadata_file_object.allow_overwrite = overwrite
        self._create_standard_format_files_object.allow_overwrite = overwrite


class Metadata:
    def __init__(self, logger=None):
        self.logger = get_logger(logger)
        self.data = {}
        self.allow_overwrite = False
        
    def add(self, metadata):
        if type(metadata) != dict:
            raise exceptions.DtypeError('metadata should be of type dict')
        self.data.update(metadata)
        
    def get(self):
        return self.data

    def set(self, metadata):
        if type(metadata) != dict:
            raise exceptions.DtypeError('metadata should be of type dict')
        self.data = metadata


class SensorInfo:
    def __init__(self, logger=None):
        self.logger = get_logger(logger)
        self.data = None

    def load_xlsx_sheet(self, file_path, sheet_name):
        wb = openpyxl.load_workbook(filename=file_path)
        if sheet_name not in wb.sheetnames:
            text = f'No worksheet named {sheet_name} in file {file_path}'
            self.logger.error(text)
            raise exceptions.PathError(text)
        ws = wb[sheet_name]
        self.data = {}
        for r, row in enumerate(ws):
            if r < 2:
                continue
            for c, cell in enumerate(row):
                if c == 0:
                    continue
                value = cell.value
                if value is None:
                    value = ''
                self.data[cell.coordinate] = str(value)

    def load_txt(self, file_path, **kwargs):
        self.data = {}
        with codecs.open(file_path, **kwargs) as fid:
            for r, line in enumerate(fid):
                split_line = line.strip('\n\r').split('\t')
                str_nr = 66
                for value in split_line:
                    col_row_str = f'{chr(str_nr)}{str(r+3)}'
                    self.data[col_row_str] = value
                    str_nr += 1


class MetadataFile:
    def __init__(self, logger=None):
        self.logger = get_logger(logger)
        self._file_path = None
        self.metadata_object = None  # source for update
        self.sensor_info_object = None
        self.allow_overwrite = False

    @property
    def file_path(self):
        return self._file_path

    @file_path.setter
    def file_path(self, file_path):
        # file_path can be both file path and directory. file_path is sett to actual file path when metadata file is created
        self._file_path = Path(file_path)
    
    @property
    def metadata(self):
        if not self.metadata_object:
            self.logger.info('No metadata added to update!')
            return {}
        return self.metadata_object.get()
    
    @property
    def overwrite_metadata(self):
        if not self.metadata_object:
            return False
        return self.metadata_object.allow_overwrite

    def change_location(self, directory):
        """
        Files will be copied to new location. Option to overwrite.
        :param directory:
        :param overwrite:
        :return:
        """
        self._assert_file_exists()
        directory = Path(directory)
        if not directory.is_dir():
            text = f'Path is not a directory: {directory}'
            self.logger.error(text)
            raise exceptions.PathError(text)
        if not directory.exists():
            os.makedirs(directory)

        new_file_path = Path(directory, self._file_path.name)
        if not self.allow_overwrite and new_file_path.exists():
            self.logger.warning(f'Permission to overwrite metadata file is set to {self.allow_overwrite}. File is not copied.')

        shutil.copyfile(self._file_path, new_file_path)
        self._file_path = new_file_path

    def add_sensorinfo_from_file(self, file_path, sheet_name=None):
        self._assert_file_exists()
        file_path = Path(file_path)
        if file_path.suffix == '.txt':
            self.sensor_info_object.load_txt(file_path)
        elif file_path.suffix == '.xlsx':
            self.sensor_info_object.load_xlsx_sheet(file_path, sheet_name=sheet_name)

        wb = openpyxl.load_workbook(self._file_path)
        ws = wb['Sensorinfo']
        for key, value in self.sensor_info_object.data.items():
            ws[key] = value
        wb.save(self._file_path)

    def _assert_file_exists(self):
        if not self._file_path.exists():
            text = f'Metadata file does not exist: {self._file_path}'
            self.logger.error(text)
            raise exceptions.MissingFiles(text)
            
            
class CNVfiles:
    def __init__(self, logger=None):
        self.logger = get_logger(logger)
        self._file_paths = None
        self.allow_overwrite = False

    @property
    def file_paths(self):
        return self._file_paths

    @file_paths.setter
    def file_paths(self, file_paths):
        if type(file_paths) in [str, Path]:
            file_paths = Path(file_paths)
            if file_paths.is_dir():
                self._file_paths = [Path(file_path) for file_path in list(generate_filepaths(file_paths,
                                                                                        pattern_list=['.cnv'],
                                                                                        only_from_dir=True))]
            else:
                self._file_paths = [file_paths]
        else:
            self._file_paths = [Path(file_path) for file_path in file_paths if file_path.endswith('.cnv')]

    def change_location(self, directory):
        """
        Files will be copied to new location. Option to overwrite.
        :param directory:
        :param overwrite:
        :return:
        """
        directory = Path(directory)
        if not directory.is_dir():
            text = f'Path is not a directory: {directory}'
            self.logger.error(text)
            raise exceptions.PathError(text)
        if not directory.exists():
            os.makedirs(directory)

        self.logger.info(f'Copying files. Permission to overwrite is set to {self.allow_overwrite}')
        file_paths = []
        for file_path in self._file_paths:
            file_name = file_path.name
            new_file_path = Path(directory, file_name)
            file_paths.append(new_file_path)
            if not self.allow_overwrite and new_file_path.exists():
                continue
            shutil.copyfile(file_path, new_file_path)
        self._file_paths = file_paths


class CreateMetadataFile:
    def __init__(self, logger=None):
        self.logger = get_logger(logger)

        self.metadata_file_object = None
        self.cnv_files_object = None

        self.allow_overwrite = False

        self.session = None

    def create_file(self):       
        self._assert_metadata_info_is_present()
        self._assert_cnv_files_info_is_present()
        self.session = ctdpy_session.Session(filepaths=self.cnv_files_object.file_paths,
                                             reader='smhi')

        datasets = self._get_datasets()
        dataset = datasets[0]
        self._update_metadata_in_dataset(dataset=dataset)
        self._save_file(dataset=dataset)

    def change_location(self, directory):
        self._assert_cnv_files_info_is_present()
        self._assert_metadata_info_is_present()
        self.cnv_files_object.change_location(directory, overwrite=self.allow_overwrite)
        self.metadata_file_object.change_location(directory, overwrite=self.allow_overwrite)

    def _get_datasets(self):
        start_time = time.time()
        datasets = self.session.read()
        self.logger.debug(f'{len(self.cnv_files_object.file_paths)} CNV files loaded in {time.time() - start_time} seconds.')
        return datasets

    def _update_metadata_in_dataset(self, dataset=None):
        
        self.session.update_metadata(datasets=dataset,
                                     metadata=self.metadata_file_object.metadata,
                                     overwrite=self.metadata_file_object.overwrite_metadata)
        self.logger.debug('Metadata updated in dataset')

    def _save_file(self, dataset=None):
        start_time = time.time()
        save_path = self.session.save_data(dataset,
                                           writer='metadata_template',
                                           return_data_path=True)
        self.logger.debug(f'Metadata file saved in {time.time() - start_time} seconds at location {save_path}')
        source_path = Path(save_path)
        target_path = self.metadata_file_object.file_path
        if target_path.is_dir():
            target_path = Path(target_path, source_path.name)
        if target_path.exists() and not self.allow_overwrite:
            text = 'Metadata file already exists and overwrite is set to False'
            self.logger.error(text)
            raise exceptions.PermissionError(text)
        shutil.copyfile(source_path, target_path)
        self.metadata_file_object.file_path = target_path  # Updated file_path if it was a directory
        self.logger.debug(f'File copied to location {target_path}')
        
    def _assert_metadata_info_is_present(self):
        text = ''
        if not self.metadata_file_object:
            text = 'No metadata file object is set by user'
        elif not self.metadata_file_object.file_path:
            text = 'File path for metadata is not set'
        elif not self.metadata_file_object.file_path.exists():
            text = 'File path for metadata does not exist'
        else:
            return
        self.logger.error(text)
        raise exceptions.MissingFiles(text)

    def _assert_cnv_files_info_is_present(self):
        if not self.cnv_files_object or not self.cnv_files_object.file_paths:
            text = 'No cnv files object is set by user'
            self.logger.error(text)
            raise exceptions.MissingFiles(text)
            

class CreateStandardFormatFiles:
    def __init__(self, logger=None):
        self.logger = get_logger(logger)

        self.metadata_file_object = None
        self.cnv_files_object = None

        self.allow_overwrite = False

        self._directory = None

    @property
    def directory(self):
        return self._directory

    @directory.setter
    def directory(self, directory):
        directory = Path(directory)
        if '.' in directory.name:
            text = f'Path is not a directory: {directory}'
            self.logger.error(text)
            raise exceptions.PathError(text)
        self._directory = directory

    def change_source_location(self, directory, overwrite=False):
        self._assert_metadata_and_cnv()
        self.cnv_files_object.change_location(directory, overwrite=overwrite)
        self.metadata_file_object.change_location(directory, overwrite=overwrite)

    def create_files(self):
        self._assert_metadata_and_cnv()
        self._assert_directory()
        all_file_paths = self.cnv_files_object.file_paths + [self.metadata_file_object.file_path]
        session = ctdpy_session.Session(filepaths=all_file_paths,
                                        reader='smhi')

        start_time = time.time()
        datasets = session.read()
        self.logger.debug(f'{len(self.cnv_files_object.file_paths)} CNV files and one metadata file loaded in {time.time() - start_time} seconds.')

        start_time = time.time()
        data_path = session.save_data(datasets,
                                      writer='ctd_standard_template',
                                      return_data_path=True,
                                      # save_path=save_directory,
                                      )

        self.logger.warning(f'Permission to overwrite existing standard format files is set to {self.allow_overwrite}')
        for file_name in os.listdir(data_path):
            source_path = Path(data_path, file_name)
            target_path = Path(self._directory, file_name)
            if target_path.exists() and not self.allow_overwrite:
                continue
            shutil.copyfile(source_path, target_path)

        self.logger.debug(f"Datasets saved in {time.time() - start_time} sec at location: {data_path}. Files copied to: {self._directory}")

    def _assert_directory(self):
        if not self._directory:
            text = 'No directory for standard format files set'
            self.logger.error(text)
            raise exceptions.MissingFiles(text)
        elif not self._directory.exists():
            os.makedirs(self._directory)

    def _assert_metadata_and_cnv(self):
        self._assert_metadata_info_is_present()
        self._assert_cnv_files_info_is_present()

    def _assert_metadata_info_is_present(self):
        if not self.metadata_file_object:
            text = 'No metadata file object is set by user'
            self.logger.error(text)
            raise exceptions.MissingFiles(text)

    def _assert_cnv_files_info_is_present(self):
        if not self.cnv_files_object or not self.cnv_files_object.file_paths:
            text = 'No cnv files object is set by user'
            self.logger.error(text)
            raise exceptions.MissingFiles(text)


def get_logger(existing_logger=None):
    if not os.path.exists('log'):
        os.makedirs('log')
    if existing_logger:
        return existing_logger
    logging.config.fileConfig('logging.conf')
    logger = logging.getLogger('timedrotating')
    return logger


if __name__ == '__main__':
    if 1:
        c = SveaController()

        c.working_directory = r'C:\mw\temp_svea'
        c.cnv_files = r'C:\mw\temp_örjan\data'

        c.set_overwrite_permission(True)
        c.create_metadata_file()

        # c.create_standard_format()

    s1 = SensorInfo()
    s1.load_xlsx_sheet(r'C:\mw\Profile\2018\SHARK_Profile_2018_BAS_DEEP\received_data/CTD sensorinfo_org.xlsx', 'Sensorinfo')

    s2 = SensorInfo()
    s2.load_txt(r'C:\mw\Profile\2018\SHARK_Profile_2018_BAS_DEEP\processed_data/sensorinfo.txt')



