import time
from pathlib import Path
import os

from ctdpy.core import session as ctdpy_session
from ctdpy.core.utils import generate_filepaths

from svea import exceptions

import logging
import logging.config
import logging.handlers


class SveaController:
    def __init__(self, logger=None):
        if not logger:
            create_log_directory()
            logging.config.fileConfig('logging.conf')
            logger = logging.getLogger('timedrotating')
        self.logger = logger
        self._working_directory = None
        self.logger.info('SveaController created')

    @property
    def working_directory(self):
        return self._working_directory

    @working_directory.setter
    def working_directory(self, directory):
        self._working_directory = Path(directory)
        self.logger.info(f'Working directory set to: {directory}')

    def sbe_processing(self):
        pass

    def create_metadata_file(self):
        pass

    def create_standard_format(self):
        pass

    def perform_automatic_qc(self):
        pass

    def open_visual_qc(self):
        pass

    def send_files_to_ftp(self):
        pass

    def import_to_lims(self):
        pass

    def create_station_plots(self):
        pass


class CreateMetadataFile:
    def __init__(self, logger=None):
        if not logger:
            create_log_directory()
            logging.config.fileConfig('logging.conf')
            logger = logging.getLogger('timedrotating')
        self.logger = logger

        self.cnv_source_files = []
        self.metadata = {}
        self.allow_overwrite_metadata = False
        self.session = None

    def set_cnv_files(self, file_paths=[], directory=None):
        if directory:
            file_paths = generate_filepaths(directory, pattern_list=['.cnv'])
        self.cnv_source_files = file_paths

    def set_metadata(self, **kwargs):
        self.metadata = kwargs

    def set_metadata_overwrite_permission(self, allow):
        if type(allow) != bool:
            text = 'Datatype for overwriting metadata has to be boolean'
            self.logger.error(text)
            raise exceptions.DtypeError(text)
        self.allow_overwrite_metadata = allow

    def set_sensorinfo(self):
        pass

    def create_file(self, file_path):
        if not self.cnv_source_files:
            text = 'No cnv files selected for creating metadata file!'
            self.logger.error(text)
            raise exceptions.MissingFiles(text)
        self.session = ctdpy_session.Session(filepaths=self.cnv_source_files,
                                             reader='smhi')

    def _get_datasets(self):
        start_time = time.time()
        datasets = self.session.read()
        self.logger.debug(f'{len(self.cnv_source_files)} CNV files loaded in {time.time() - start_time} seconds.')
        return datasets

    def _update_metadata_in_dataset(self, dataset):
        self.logger.debug(f'Overwrite metadata is set to {self.allow_overwrite_metadata}')
        self.session.update_metadata(datasets=dataset, metadata=self.metadata, overwrite=self.allow_overwrite_metadata)
        self.logger.debug('Metadata updated in dataset')

    def save_file(self, file_path):
        pass


def create_log_directory():
    if not os.path.exists('log'):
        os.makedirs('log')

if __name__ == '__main__':
    c = SveaController()



