import glob
import logging
import pandas as pd
import os
import numpy as np

from apercal.modules.base import BaseModule
#from apercal.subs import irods as subs_irods
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from getdata_alta import getdata_alta, getstatus_alta
from apercal.libs import lib
from apercal.subs.msutils import flip_ra

logger = logging.getLogger(__name__)


class prepare(BaseModule):
    """
    Prepare class. Automatically copies the datasets into the directories and selects valid data (in case of multi-element observations)
    """
    module_name = 'PREPARE'

    prepare_date = None
    prepare_obsnum_fluxcal = None
    prepare_obsnum_polcal = None
    prepare_obsnum_target = None
    prepare_target_beams = None
    prepare_bypass_alta = None
    prepare_flip_ra = False
    prepare_split = None
    prepare_split_startchannel = None
    prepare_split_endchannel = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)

    def go(self):
        """
        Executes the complete prepare step with the parameters indicated in the config-file in the following order:
        copyobs
        """
        logger.info('Preparing data for calibration')
        self.copyobs()
        #self.split()
        logger.info('Data prepared for calibration')

    ##############################################
    # Continuum mosaicing of the stacked images #
    ##############################################

    def copyobs(self):
        """
        Prepares the directory structure and copies over the needed data from ALTA.
        Checks for data in the current working directories and copies only missing data.
        """
        subs_setinit.setinitdirs(self)

        # Check if the parameter is already in the parameter file and load it otherwise create the needed arrays #

        if not os.path.isdir(self.basedir):
            os.mkdir(self.basedir)

        # Is the fluxcal data requested?
        preparefluxcalrequested = get_param_def(self, 'prepare_fluxcal_requested', False)

        # Is the polcal data requested?
        preparepolcalrequested = get_param_def(self, 'prepare_polcal_requested', False)

        # Is the target data requested? One entry per beam
        preparetargetbeamsrequested = get_param_def(self, 'prepare_targetbeams_requested', np.full(self.NBEAMS, False))

        # Is the fluxcal data already on disk?
        preparefluxcaldiskstatus = get_param_def(self, 'prepare_fluxcal_diskstatus', False)

        # Is the polcal data already on disk?
        preparepolcaldiskstatus = get_param_def(self, 'prepare_polcal_diskstatus', False)

        # Is the target data already on disk? One entry per beam
        preparetargetbeamsdiskstatus = get_param_def(self, 'prepare_targetbeams_diskstatus', np.full(self.NBEAMS, False))

        # Is the fluxcal data on ALTA?
        preparefluxcalaltastatus = get_param_def(self, 'prepare_fluxcal_altastatus', False)

        # Is the polcal data on ALTA?
        preparepolcalaltastatus = get_param_def(self, 'prepare_polcal_altastatus', False)

        # Is the target data on disk? One entry per beam
        preparetargetbeamsaltastatus = get_param_def(self, 'prepare_targetbeams_altastatus', np.full(self.NBEAMS, False))

        # Is the fluxcal data copied?
        preparefluxcalcopystatus = get_param_def(self, 'prepare_fluxcal_copystatus', False)

        # Is the polcal data on copied?
        preparepolcalcopystatus = get_param_def(self, 'prepare_polcal_copystatus', False)

        # Is the target data copied? One entry per beam
        preparetargetbeamscopystatus = get_param_def(self, 'prepare_targetbeams_copystatus', np.full(self.NBEAMS, False))

        # Reason for flux calibrator dataset not being there
        preparefluxcalrejreason = get_param_def(self, 'prepare_fluxcal_rejreason', np.full(1, '', dtype='U50'))

        # Reason for polarisation calibrator dataset not being there
        preparepolcalrejreason = get_param_def(self, 'prepare_polcal_rejreason', np.full(1, '', dtype='U50'))

        # Reason for a beam dataset not being there
        preparetargetbeamsrejreason = get_param_def(self, 'prepare_targetbeams_rejreason', np.full(self.NBEAMS, '', dtype='U50'))

        ################################################
        # Start the preparation of the flux calibrator #
        ################################################

        if self.fluxcal != '':  # If the flux calibrator is requested
            preparefluxcalrejreason[0] = ''  # Empty the comment string
            preparefluxcalrequested = True
            fluxcal = self.get_fluxcal_path()
            preparefluxcaldiskstatus = os.path.isdir(fluxcal)
            if preparefluxcaldiskstatus:
                logger.debug('Flux calibrator dataset found on disk ({})'.format(fluxcal))
            else:
                logger.debug('Flux calibrator dataset not on disk ({})'.format(fluxcal))

            if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                logger.debug("Skipping fetching dataset from ALTA")
            else:
                # Check if the flux calibrator dataset is available on ALTA
                preparefluxcalaltastatus = getstatus_alta(self.prepare_date, self.prepare_obsnum_fluxcal,
                                                                     self.beam)
                if preparefluxcalaltastatus:
                    logger.debug('Flux calibrator dataset available on ALTA')
                else:
                    logger.warning('Flux calibrator dataset not available on ALTA')
                # Copy the flux calibrator data from ALTA if needed
                if preparefluxcaldiskstatus and preparefluxcalaltastatus:
                    preparefluxcalcopystatus = True
                elif preparefluxcaldiskstatus and not preparefluxcalaltastatus:
                    preparefluxcalcopystatus = True
                    logger.warning('Flux calibrator data available on disk, but not in ALTA!')
                elif not preparefluxcaldiskstatus and preparefluxcalaltastatus:
                    subs_managefiles.director(self, 'mk', self.basedir + self.beam + '/' + self.rawsubdir, verbose=False)
                    getdata_alta(int(self.prepare_date), int(self.prepare_obsnum_fluxcal), 0, targetdir=self.rawdir + '/' + self.fluxcal)
                    if os.path.isdir(self.get_fluxcal_path()):
                        preparefluxcalcopystatus = True
                        logger.debug('Flux calibrator dataset successfully copied from ALTA')
                    else:
                        preparefluxcalcopystatus = False
                        preparefluxcalrejreason[0] = 'Copy from ALTA not successful'
                        logger.error('Flux calibrator dataset available on ALTA, but NOT successfully copied!')
                    if self.prepare_flip_ra:
                        flip_ra(self.rawdir + '/' + self.fluxcal, logger=logger)
                elif not preparefluxcaldiskstatus and not preparefluxcalaltastatus:
                    preparefluxcalcopystatus = False
                    preparefluxcalrejreason[0] = 'Dataset not on ALTA or disk'
                    logger.error('Flux calibrator dataset not available on disk nor in ALTA! The next steps will not work!')
        else:  # In case the flux calibrator is not specified meaning the parameter is empty.
            preparefluxcalrequested = False
            preparefluxcaldiskstatus = False
            preparefluxcalaltastatus = False
            preparefluxcalcopystatus = False
            preparefluxcalrejreason[0] = 'Dataset not specified'
            logger.error('No flux calibrator dataset specified. The next steps will not work!')

        # Save the derived parameters for the fluxcal to the parameter file

        subs_param.add_param(self, 'prepare_fluxcal_requested', preparefluxcalrequested)
        subs_param.add_param(self, 'prepare_fluxcal_diskstatus', preparefluxcaldiskstatus)
        subs_param.add_param(self, 'prepare_fluxcal_altastatus', preparefluxcalaltastatus)
        subs_param.add_param(self, 'prepare_fluxcal_copystatus', preparefluxcalcopystatus)
        subs_param.add_param(self, 'prepare_fluxcal_rejreason', preparefluxcalrejreason)

        ########################################################
        # Start the preparation of the polarisation calibrator #
        ########################################################

        if self.polcal != '':  # If the polarised calibrator is requested
            preparepolcalrejreason[0] = ''  # Empty the comment string
            preparepolcalrequested = True
            preparepolcaldiskstatus = os.path.isdir(self.get_polcal_path())
            if preparepolcaldiskstatus:
                logger.debug('Polarisation calibrator dataset found on disk')
            else:
                logger.debug('Polarisation calibrator dataset not on disk')

            if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                logger.debug("Skipping fetching dataset from ALTA")
            else:

                # Check if the polarisation calibrator dataset is available on ALTA
                preparepolcalaltastatus = getstatus_alta(self.prepare_date, self.prepare_obsnum_polcal, self.beam)
                if preparepolcalaltastatus:
                    logger.debug('Polarisation calibrator dataset available on ALTA')
                else:
                    logger.warning('Polarisation calibrator dataset not available on ALTA')
                # Copy the polarisation calibrator data from ALTA if needed
                if preparepolcaldiskstatus and preparepolcalaltastatus:
                    preparepolcalcopystatus = True
                elif preparepolcaldiskstatus and not preparepolcalaltastatus:
                    preparepolcalcopystatus = True
                    logger.warning('Polarisation calibrator data available on disk, but not in ALTA!')
                elif not preparepolcaldiskstatus and preparepolcalaltastatus:
                    subs_managefiles.director(self, 'mk', self.basedir + self.beam + '/' + self.rawsubdir, verbose=False)
                    getdata_alta(int(self.prepare_date), int(self.prepare_obsnum_polcal), 0, targetdir=self.rawdir + '/' + self.polcal)
                    if os.path.isdir(self.get_polcal_path()):
                        preparepolcalcopystatus = True
                        logger.debug('Polarisation calibrator dataset successfully copied from ALTA')
                    else:
                        preparepolcalcopystatus = False
                        preparepolcalrejreason[0] = 'Copy from ALTA not successful'
                        logger.error('Polarisation calibrator dataset available on ALTA, but NOT successfully copied!')
                    if self.prepare_flip_ra:
                        flip_ra(self.rawdir + '/' + self.polcal, logger=logger)
                elif not preparepolcaldiskstatus and not preparepolcalaltastatus:
                    preparepolcalcopystatus = False
                    preparepolcalrejreason[0] = 'Dataset not on ALTA or disk'
                    logger.warning('Polarisation calibrator dataset not available on disk nor in ALTA! Polarisation calibration will not work!')
        else:  # In case the polarisation calibrator is not specified meaning the parameter is empty.
            preparepolcalrequested = False
            preparepolcaldiskstatus = False
            preparepolcalaltastatus = False
            preparepolcalcopystatus = False
            preparepolcalrejreason[0] = 'Dataset not specified'
            logger.warning('No polarisation calibrator dataset specified. Polarisation calibration will not work!')

        # Save the derived parameters for the polcal to the parameter file

        subs_param.add_param(self, 'prepare_polcal_requested', preparepolcalrequested)
        subs_param.add_param(self, 'prepare_polcal_diskstatus', preparepolcaldiskstatus)
        subs_param.add_param(self, 'prepare_polcal_altastatus', preparepolcalaltastatus)
        subs_param.add_param(self, 'prepare_polcal_copystatus', preparepolcalcopystatus)
        subs_param.add_param(self, 'prepare_polcal_rejreason', preparepolcalrejreason)

        ################################################
        # Start the preparation of the target datasets #
        ################################################

        if self.prepare_obsnum_target and self.prepare_obsnum_target != '':
            if self.prepare_target_beams == 'all':  # if all beams are requested
                reqbeams_int = range(self.NBEAMS)  # create a list of numbers for the beams
                reqbeams = [str(b).zfill(2) for b in reqbeams_int]  # Add the leading zeros
            else:  # if only certain beams are requested
                reqbeams = self.prepare_target_beams.split(",")
                reqbeams_int = [int(b) for b in reqbeams]
                reqbeams = [str(b).zfill(2) for b in reqbeams_int] # Add leading zeros
            for beam in reqbeams:
                preparetargetbeamsrequested[int(beam)] = True
            for b in reqbeams_int:
                # Check which target beams are already on disk
                preparetargetbeamsrejreason[int(b)] = ''  # Empty the comment string
                preparetargetbeamsdiskstatus[b] = os.path.isdir(
                    self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target)
                if preparetargetbeamsdiskstatus[b]:
                    logger.debug('Target dataset for beam ' + str(b).zfill(2) + ' found on disk')
                else:
                    logger.debug('Target dataset for beam ' + str(b).zfill(2) + ' NOT found on disk')

                if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                    logger.debug("Skipping fetching dataset from ALTA")
                else:
                    # Check which target datasets are available on ALTA
                    preparetargetbeamsaltastatus[b] = getstatus_alta(self.prepare_date, self.prepare_obsnum_target, str(b).zfill(2))
                    if preparetargetbeamsaltastatus[b]:
                        logger.debug('Target dataset for beam ' + str(b).zfill(2) + ' available on ALTA')
                    else:
                        logger.debug('Target dataset for beam ' + str(b).zfill(2) + ' NOT available on ALTA')

            if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                logger.debug("Skipping fetching dataset from ALTA")
            else:
                # Set the copystatus of the beams and copy beams which are requested but not on disk
                for c in reqbeams_int:
                    if preparetargetbeamsdiskstatus[c] and preparetargetbeamsaltastatus[c]:
                        preparetargetbeamscopystatus[c] = True
                    elif preparetargetbeamsdiskstatus[c] and not preparetargetbeamsaltastatus[c]:
                        preparetargetbeamscopystatus[c] = True
                        logger.warning('Target dataset for beam ' + str(c).zfill(2) + ' available on disk, but not in ALTA!')
                    elif not preparetargetbeamsdiskstatus[c] and preparetargetbeamsaltastatus[c] and str(c).zfill(2) in reqbeams:  # if target dataset is requested, but not on disk
                        subs_managefiles.director(self, 'mk', self.basedir + str(c).zfill(2) + '/' + self.rawsubdir, verbose=False)
                        getdata_alta(int(self.prepare_date), int(self.prepare_obsnum_target), int(str(c).zfill(2)), targetdir=self.basedir + str(c).zfill(2) + '/' + self.rawsubdir + '/' + self.target)
                        # Check if copy was successful
                        if os.path.isdir(self.basedir + str(c).zfill(2) + '/' + self.rawsubdir + '/' + self.target):
                            preparetargetbeamscopystatus[c] = True
                        else:
                            preparetargetbeamscopystatus[c] = False
                            preparetargetbeamsrejreason[int(c)] = 'Copy from ALTA not successful'
                            logger.error('Target beam dataset available on ALTA, but NOT successfully copied!')
                        if self.prepare_flip_ra:
                            flip_ra(self.basedir + str(c).zfill(2) + '/' + self.rawsubdir + '/' + self.target, logger=logger)
                    elif not preparetargetbeamsdiskstatus[c] and not preparetargetbeamsaltastatus[c] and str(c).zfill(2) in reqbeams:
                        preparetargetbeamscopystatus[c] = False
                        preparetargetbeamsrejreason[int(c)] = 'Dataset not on ALTA or disk'
                        logger.error('Target beam dataset not available on disk nor in ALTA! Requested beam cannot be processed!')
        else:  # If no target dataset is requested meaning the parameter is empty
            logger.warning('No target datasets specified!')
            for b in range(self.NBEAMS):
                preparetargetbeamsrequested[b] = False
                preparetargetbeamsdiskstatus[b] = False
                preparetargetbeamsaltastatus[b] = False
                preparetargetbeamscopystatus[b] = False
                preparetargetbeamsrejreason[int(b)] = 'Dataset not specified'

        # Save the derived parameters for the target beams to the parameter file

        subs_param.add_param(self, 'prepare_targetbeams_requested', preparetargetbeamsrequested)
        subs_param.add_param(self, 'prepare_targetbeams_diskstatus', preparetargetbeamsdiskstatus)
        subs_param.add_param(self, 'prepare_targetbeams_altastatus', preparetargetbeamsaltastatus)
        subs_param.add_param(self, 'prepare_targetbeams_copystatus', preparetargetbeamscopystatus)
        subs_param.add_param(self, 'prepare_targetbeams_rejreason', preparetargetbeamsrejreason)


    def split(self):
        """
        Splits out a certain frequency range from the datasets for the quicklook pipeline
        """
        if self.prepare_split:
            logger.info('Splitting channel ' + str(self.prepare_split_startchannel) + ' until ' + str(self.prepare_split_endchannel))
            # split the flux calibrator dataset
            logger.debug("self.fluxcal = {}".format(self.fluxcal))
            logger.debug("os.path.isdir(self.get_fluxcal_path()) = {}".format(
                os.path.isdir(self.get_fluxcal_path())))
            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                fluxcal_split = 'split(vis = "' + self.get_fluxcal_path() + '", outputvis = "' + self.get_fluxcal_path().rstrip('.MS') + '_split.MS"' + ', spw = "0:' + str(self.prepare_split_startchannel) + '~' + str(self.prepare_split_endchannel) + '", datacolumn = "data")'
                lib.run_casa([fluxcal_split], log_output=True, timeout=3600)
                if os.path.isdir(self.get_fluxcal_path().rstrip('.MS') + '_split.MS'):
                    subs_managefiles.director(self, 'rm', self.get_fluxcal_path())
                    subs_managefiles.director(self, 'rn', self.get_fluxcal_path(), file_=self.get_fluxcal_path().rstrip('.MS') + '_split.MS')
                else:
                    logger.warning('Splitting of flux calibrator dataset not successful!')
            else:
                logger.warning('Fluxcal not set or dataset not available! Cannot split flux calibrator dataset!')
            # Split the polarised calibrator dataset
            logger.debug("self.polcal = {}".format(self.polcal))
            logger.debug("os.path.isdir(self.get_polcal_path()) = {}".format(
                os.path.isdir(self.get_polcal_path())))
            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                polcal_split = 'split(vis = "' + self.get_polcal_path() + '", outputvis = "' + self.get_polcal_path().rstrip('.MS') + '_split.MS"' + ', spw = "0:' + str(self.prepare_split_startchannel) + '~' + str(self.prepare_split_endchannel) + '", datacolumn = "data")'
                lib.run_casa([polcal_split], log_output=True, timeout=3600)
                if os.path.isdir(self.get_polcal_path().rstrip('.MS') + '_split.MS'):
                    subs_managefiles.director(self, 'rm', self.get_polcal_path())
                    subs_managefiles.director(self, 'rn', self.get_polcal_path(), file_=self.get_polcal_path().rstrip('.MS') + '_split.MS')
                else:
                    logger.warning('Splitting of polarised calibrator dataset not successful!')
            else:
                logger.warning('Polcal not set or dataset not available! Cannot split polarised calibrator dataset!')
            # Split the target dataset
            logger.debug("self.target = {}".format(self.target))
            logger.debug("os.path.isdir(self.get_target_path()) = {}".format(
                os.path.isdir(self.get_target_path())))
            if self.target != '' and os.path.isdir(self.get_target_path()):
                target_split = 'split(vis = "' + self.get_target_path() + '", outputvis = "' + self.get_target_path().rstrip('.MS') + '_split.MS"' + ', spw = "0:' + str(self.prepare_split_startchannel) + '~' + str(self.prepare_split_endchannel) + '", datacolumn = "data")'
                lib.run_casa([target_split], log_output=True, timeout=3600)
                if os.path.isdir(self.get_target_path().rstrip('.MS') + '_split.MS'):
                    subs_managefiles.director(self, 'rm', self.get_target_path())
                    subs_managefiles.director(self, 'rn', self.get_target_path(), file_=self.get_target_path().rstrip('.MS') + '_split.MS')
                else:
                    logger.warning('Splitting of target dataset not successful!')
            else:
                logger.warning('Target not set or dataset not available! Cannot split target dataset!')
        else:
            pass


    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during PREPARE. No detailed summary
        is available for PREPARE

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in notebook
        """

        # Load the parameters from the parameter file

        FR = subs_param.get_param(self, 'prepare_fluxcal_requested')
        FD = subs_param.get_param(self, 'prepare_fluxcal_diskstatus')
        FA = subs_param.get_param(self, 'prepare_fluxcal_altastatus')
        FC = subs_param.get_param(self, 'prepare_fluxcal_copystatus')
        Frej = subs_param.get_param(self, 'prepare_fluxcal_rejreason')
        PR = subs_param.get_param(self, 'prepare_polcal_requested')
        PD = subs_param.get_param(self, 'prepare_polcal_diskstatus')
        PA = subs_param.get_param(self, 'prepare_polcal_altastatus')
        PC = subs_param.get_param(self, 'prepare_polcal_copystatus')
        Prej = subs_param.get_param(self, 'prepare_polcal_rejreason')
        TR = subs_param.get_param(self, 'prepare_targetbeams_requested')
        TD = subs_param.get_param(self, 'prepare_targetbeams_diskstatus')
        TA = subs_param.get_param(self, 'prepare_targetbeams_altastatus')
        TC = subs_param.get_param(self, 'prepare_targetbeams_copystatus')
        Trej = subs_param.get_param(self, 'prepare_targetbeams_rejreason')

        # Create the data frame

        beam_range = range(self.NBEAMS)
        dataset_beams = [self.target[:-3] + ' Beam ' + str(b).zfill(2) for b in beam_range]
        dataset_indices = ['Flux calibrator (' + self.fluxcal[:-3] + ')', 'Polarised calibrator (' + self.polcal[:-3] + ')'] + dataset_beams

        all_r = np.full(self.NBEAMS + 2, False)
        all_r[0] = FR
        all_r[1] = PR
        all_r[2:] = TR

        all_d = np.full(self.NBEAMS + 2, False)
        all_d[0] = FD
        all_d[1] = PD
        all_d[2:] = TD

        all_a = np.full(self.NBEAMS + 2, False)
        all_a[0] = FA
        all_a[1] = PA
        all_a[2:] = TA

        all_c = np.full(self.NBEAMS + 2, False)
        all_c[0] = FC
        all_c[1] = PC
        all_c[2:] = TC

        all_rej = np.concatenate((Frej, Prej, Trej), axis=0)

        df_req = pd.DataFrame(np.ndarray.flatten(all_r), index=dataset_indices, columns=['Requested?'])
        df_disk = pd.DataFrame(np.ndarray.flatten(all_d), index=dataset_indices, columns=['On disk?'])
        df_alta = pd.DataFrame(np.ndarray.flatten(all_a), index=dataset_indices, columns=['On ALTA?'])
        df_copy = pd.DataFrame(np.ndarray.flatten(all_c), index=dataset_indices, columns=['Copied?'])
        df_rej = pd.DataFrame(all_rej, index=dataset_indices, columns=['Comment'])

        df = pd.concat([df_req, df_disk, df_alta, df_copy, df_rej], axis=1)

        return df

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in this step!
        """
        subs_setinit.setinitdirs(self)
        logger.warning('Deleting all raw data products and their directories.')
        subs_managefiles.director(self, 'ch', self.basedir)
        deldirs = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir)
        for dir_ in deldirs:
            subs_managefiles.director(self, 'rm', dir_)
        logger.warning('Deleting all parameter file entries for PREPARE module')
        subs_param.del_param(self, 'prepare_fluxcal_requested')
        subs_param.del_param(self, 'prepare_fluxcal_diskstatus')
        subs_param.del_param(self, 'prepare_fluxcal_altastatus')
        subs_param.del_param(self, 'prepare_fluxcal_copystatus')
        subs_param.del_param(self, 'prepare_fluxcal_rejreason')
        subs_param.del_param(self, 'prepare_polcal_requested')
        subs_param.del_param(self, 'prepare_polcal_diskstatus')
        subs_param.del_param(self, 'prepare_polcal_altastatus')
        subs_param.del_param(self, 'prepare_polcal_copystatus')
        subs_param.del_param(self, 'prepare_polcal_rejreason')
        subs_param.del_param(self, 'prepare_targetbeams_requested')
        subs_param.del_param(self, 'prepare_targetbeams_diskstatus')
        subs_param.del_param(self, 'prepare_targetbeams_altastatus')
        subs_param.del_param(self, 'prepare_targetbeams_copystatus')
        subs_param.del_param(self, 'prepare_targetbeams_rejreason')
