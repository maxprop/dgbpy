from inspect import isclass
from bokeh.server.server import Server
import dgbpy.uibokeh_well as odb
import odpy.common as odcommon
import argparse, os, sys
from dgbpy.bokehserver import StartBokehServer, DefineBokehArguments

undef = 1e30
survargs= odcommon.getODArgs()
wellnm = 'None'
logs = []

import dgbpy.servicemgr as dgbservmgr

parser = argparse.ArgumentParser(
            description='Select parameters for machine learning model training')
parser.add_argument( '-v', '--version',
            action='version', version='%(prog)s 1.0' )
parser.add_argument( 'h5file',
            type=argparse.FileType('r'),
            help='HDF5 file containing the training data' )
datagrp = parser.add_argument_group( 'Data' )
datagrp.add_argument( '--dataroot',
            dest='dtectdata', metavar='DIR', nargs=1,
            help='Survey Data Root' )
datagrp.add_argument( '--survey',
            dest='survey', nargs=1,
            help='Survey name' )
traingrp = parser.add_argument_group( 'Training' )
traingrp.add_argument( '--modelfnm',
            dest='model', nargs=1,
            type=argparse.FileType('r'),
            help='Input model file name' )
traingrp.add_argument( '--transfer', '--Transfer', dest='transfer',
            action='store_true', default=False,
            help='Do transfer training' )
traingrp.add_argument( '--trainmodelnm',
            dest='trainmodelnm', nargs='?', default='',
            help='Output trained model dataset name' )
traingrp.add_argument( '--mldir',
            dest='mldir', nargs=1,
            help='Machine Learning Logging Base Directory' )
odappl = parser.add_argument_group( 'OpendTect application' )
odappl.add_argument( '--dtectexec',
            metavar='DIR', nargs=1,
            help='Path to OpendTect executables' )
odappl.add_argument( '--qtstylesheet',
            metavar='qss', nargs=1,
            type=argparse.FileType('r'),
            help='Qt StyleSheet template' )
loggrp = parser.add_argument_group( 'Logging' )
loggrp.add_argument( '--proclog',
            dest='logfile', metavar='file', nargs='?',
            type=argparse.FileType('a'), default=sys.stdout,
            help='Progress report output' )
loggrp.add_argument( '--syslog',
            dest='sysout', metavar='stdout', nargs='?',
            type=argparse.FileType('a'), default=sys.stdout,
            help='Standard output' )

parser = DefineBokehArguments(parser)

args = vars(parser.parse_args())

def training_app(doc):
# Keep all lengthy operations below
  import logging
  logging.getLogger('bokeh.bokeh_machine_learning.main').setLevel(logging.DEBUG)
  odcommon.proclog_logger = logging.getLogger('bokeh.bokeh_machine_learning.main')

  class MsgHandler(logging.StreamHandler):
    def __init__(self, msgstr, servmgr, msgkey, msgjson):
      logging.StreamHandler.__init__(self)
      self.msgstr = msgstr
      self.servmgr = servmgr
      self.msgkey = msgkey
      self.msgjson = msgjson

    def emit(self, record):
      try:
        logmsg = self.format(record)
        if self.msgstr in logmsg:
          doc.add_next_tick_callback(self.sendmsg)
      except (KeyboardInterrupt, SystemExit):
          raise
      except:
          self.handleError(record)

    def sendmsg(self):
      self.servmgr.sendObject(self.msgkey, self.msgjson)

  odcommon.log_msg( 'Start training UI')
  from os import path
  import psutil
  from functools import partial

  from bokeh.layouts import column, row
  from bokeh.models.widgets import Panel, Select, Tabs
  from bokeh.models import CheckboxGroup

  from odpy.oscommand import (getPythonCommand, execCommand, kill,
                            isRunning, pauseProcess, resumeProcess)
  import dgbpy.keystr as dgbkeys
  from dgbpy import mlapply as dgbmlapply
  from dgbpy import uibokeh, uikeras, uisklearn, uitorch
  from dgbpy import mlio as dgbmlio

  trainingcb = None
  traintype =  dgbmlapply.TrainType.New
  doabort = False

  examplefilenm = args['h5file'].name
  if 'model' in args:
    model = args['model']
    if model != None and len(model)>0:
      model = model[0].name
      if args['transfer']:
        traintype = dgbmlapply.TrainType.Transfer
      else:
        traintype = dgbmlapply.TrainType.Resume

  trainscriptfp = path.join(path.dirname(path.dirname(__file__)),'mlapplyrun.py')

  with dgbservmgr.ServiceMgr(args['bsmserver'], args['ppid'],args['port'],args['bokehid']) as this_service:
    traintabnm = 'Training'
    paramtabnm = 'Parameters'

    mh = MsgHandler('--Training Started--', this_service, 'ml_training_msg',
                    {'training_started': ''})
    mh.setLevel(logging.DEBUG)
    odcommon.proclog_logger.addHandler(mh)
    
    trainpanel = Panel(title=traintabnm)
    parameterspanel = Panel(title=paramtabnm)
    mainpanel = Tabs(tabs=[trainpanel,parameterspanel])

    ML_PLFS = []
    ML_PLFS.append( uikeras.getPlatformNm(True) )
    ML_PLFS.append( uisklearn.getPlatformNm(True) )
    ML_PLFS.append( uitorch.getPlatformNm(True) )

    platformfld = Select(title="Machine learning platform:",options=ML_PLFS)
    tensorboardfld = CheckboxGroup(labels=['Clear Tensorboard log files'], inline=True,
                                   active=[], visible=True)

    info = None
    keraspars = None
    torchpars = None
    sklearnpars = None
    parsgroups = None
    traininglogfilenm = 'process_log_1'

    def makeUI(examplefilenm):
      nonlocal info
      nonlocal keraspars
      nonlocal torchpars
      nonlocal sklearnpars
      nonlocal parsgroups
      info = dgbmlio.getInfo( examplefilenm, quick=True )
      isclassification = info[dgbkeys.classdictstr]
      uikeras.info = info
      uitorch.info = info
      uisklearn.info = info
      keraspars = uikeras.getUiPars()
      torchpars = uitorch.getUiPars()
      sklearnpars = uisklearn.getUiPars(isclassification)
      parsgroups = (keraspars,sklearnpars,torchpars)
      platformfld.disabled = False

    def updateUI():
      nonlocal info
      nonlocal keraspars
      nonlocal torchpars
      nonlocal platformfld
      keraspars['uiobjects']['dodecimatefld'].active = []
      keraspars['uiobjects']['sizefld'].text = uikeras.getSizeStr(info[dgbkeys.estimatedsizedictstr])

    makeUI(examplefilenm)
    updateUI()

    def resetUiFields(cb):
      nonlocal keraspars
      nonlocal sklearnpars
      nonlocal torchpars
      platformnm = platformfld.value
      if platformnm == uikeras.getPlatformNm():
        keraspars = uikeras.getUiPars(keraspars)
      elif platformnm == uitorch.getPlatformNm():
        torchpars = uitorch.getUiPars(torchpars)
      elif platformnm == uisklearn.getPlatformNm():
        sklearnpars = uisklearn.getUiPars(sklearnpars)

    parsresetbut = uibokeh.getButton('Reset', callback_fn=resetUiFields)

    parsbackbut = uibokeh.getButton('Back',\
      callback_fn=partial(uibokeh.setTabFromButton,panelnm=mainpanel,tabnm=traintabnm))

    def procArgChgCB( paramobj ):
      nonlocal examplefilenm
      nonlocal model
      nonlocal traintype
      nonlocal info
      nonlocal traininglogfilenm
      for key, val in paramobj.items():
        if key=='Training Type':
          odcommon.log_msg(f'Change training type to "{val}".')
          if val == dgbmlapply.TrainType.New.name:
            traintype = dgbmlapply.TrainType.New
            model = None
          elif val == dgbmlapply.TrainType.Resume.name:
            traintype = dgbmlapply.TrainType.Resume
          elif val == dgbmlapply.TrainType.Transfer.name:
            traintype = dgbmlapply.TrainType.Transfer
        elif key=='Input Model File':
          odcommon.log_msg(f'Change pretrained input model to "{val}".')
          if os.path.isfile(val):
            model = val
          else:
            model = None
            traintype = dgbmlapply.TrainType.New
        elif key=='ProcLog File':
          odcommon.log_msg(f'Change log file name to "{val}".')
          traininglogfilenm = val
        elif key=='Output Model File':
          odcommon.log_msg(f'Change output model to "{val}".')
          doRun( doTrain(val) )
        elif key=='Examples File':
          odcommon.log_msg(f'Change input example data to "{val}".')
          if examplefilenm != val:
            examplefilenm = val
            info = dgbmlio.getInfo( examplefilenm, quick=True )
            uikeras.info = info
            doc.add_next_tick_callback(partial(updateUI))
      return dict()

    this_service.addAction('BokehParChg', procArgChgCB )

    def mlchgCB( attrnm, old, new):
      nonlocal tensorboardfld
      selParsGrp( new )
      if new==uikeras.getPlatformNm(True)[0]:
          tensorboardfld.visible = True
      else:
          tensorboardfld.visible = False

    def getParsGrp( platformnm ):
      for platform,parsgroup in zip(ML_PLFS,parsgroups):
        if platform[0] == platformnm:
          return parsgroup['grp']
      return None

    def selParsGrp( platformnm ):
      parsgrp = getParsGrp( platformnm )
      if parsgrp == None:
        return
      doc.clear()
      parameterspanel.child = column( parsgrp, row(parsresetbut, parsbackbut))
      doc.add_root(mainpanel)
      this_service.sendObject('ml_training_msg', {'platform_change': platformnm})

    def getUiParams():
      parsgrp = getParsGrp( platformfld.value )
      if platformfld.value == uikeras.getPlatformNm():
        return uikeras.getUiParams( keraspars )
      elif platformfld.value == uisklearn.getPlatformNm():
        return uisklearn.getUiParams( sklearnpars )
      elif platformfld.value == uitorch.getPlatformNm():
        return uitorch.getUiParams( torchpars )
      return {}

    def getProcArgs( platfmnm, pars, outnm ):
      ret = {
        'posargs': [examplefilenm],
        'odargs': odcommon.getODArgs( args ),
        'dict': {
          'platform': platfmnm,
          'parameters': pars,
          'output': outnm
        }
      }
      dict = ret['odargs']
      dict.update({'proclog': traininglogfilenm})
      print(dict)
      dict = ret['dict']
      if model != None:
        dict.update({'model': model})

      if 'mldir' in args:
        mldir = args['mldir']
        if mldir != None and len(mldir)>0:
          dict.update({'logdir': mldir[0]})
          dict.update({'cleanlogdir': len(tensorboardfld.active)!=0})
      dict.update({dgbkeys.learntypedictstr: traintype.name})
      return ret

    def doRun( cb = None ):
      nonlocal trainingcb
      nonlocal doabort
      doabort = False
      if cb == None:
        this_service.sendObject('ml_training_msg', {'training can start request': ''})
        return True
      elif cb == False:
        doabort = True
        return False
      else:
        trainingcb = {uibokeh.timerkey: cb}
      return True

    def doTrain( trainedfnm ):
      if len(trainedfnm) < 1:
        return False
      if platformfld.value==uikeras.getPlatformNm() and 'divfld' in keraspars['uiobjects']:
            odcommon.log_msg('\nNo Keras models found for this workflow.')
            return False

      modelnm = trainedfnm

      scriptargs = getProcArgs( platformfld.value, getUiParams(), \
                                modelnm )
      cmdtorun = getPythonCommand( trainscriptfp, scriptargs['posargs'], \
                              scriptargs['dict'], scriptargs['odargs'] )

      if platformfld.value == uikeras.getPlatformNm():
          this_service.sendObject('ml_training_msg', {'start tensorboard': ''})

      return execCommand( cmdtorun, background=True )

    def doAbort( proc ):
      if isRunning(proc):
        proc = kill( proc )
      return None

    def doPause( proc ):
      pauseProcess( proc )
      return proc

    def doResume( proc ):
      resumeProcess( proc )
      return proc

    def trainMonitorCB( rectrainingcb ):
      proc = rectrainingcb[uibokeh.timerkey]
      nonlocal trainingcb
      nonlocal doabort
      if doabort:
        return (False,rectrainingcb)
      if proc == None:
        if trainingcb != None and uibokeh.timerkey in trainingcb:
          rectrainingcb[uibokeh.timerkey] = trainingcb[uibokeh.timerkey]
        return (True,rectrainingcb)
      if isRunning(proc):
        return (True,rectrainingcb)
      try:
        stat = proc.status()
      except psutil.NoSuchProcess:
        if not odcommon.batchIsFinished( traininglogfilenm ):
          odcommon.log_msg( '\nProcess is no longer running (crashed or terminated).' )
          odcommon.log_msg( 'See OpendTect log file for more details (if available).' )
        else:
          this_service.sendObject('ml_training_msg', {'training_finished': ''})
        rectrainingcb[uibokeh.timerkey] = None
        trainingcb[uibokeh.timerkey] = None
        return (False,rectrainingcb)
      return (True,rectrainingcb)

    platformfld.on_change('value',mlchgCB)
    buttonsgrp = uibokeh.getRunButtonsBar( doRun, doAbort, doPause, doResume, trainMonitorCB )
    trainpanel.child = column( platformfld, tensorboardfld, buttonsgrp )

    def initWin():
      mllearntype = info[dgbkeys.learntypedictstr]
      if mllearntype == dgbkeys.loglogtypestr or \
        mllearntype == dgbkeys.logclustertypestr or \
        mllearntype == dgbkeys.seisproptypestr:
        platformfld.value = uisklearn.getPlatformNm(True)[0]
      else:
        platformfld.value = uikeras.getPlatformNm(True)[0]
      mlchgCB( 'value', 0, platformfld.value )
      doc.title = 'Machine Learning'

    initWin()

def training_app1(doc):
  well = odb.Well(wellnm, args=survargs)
  ltmgr = odb.LogTrackMgr(well, deflogs=logs, trackwidth=400, withui=True)
  doc.add_root(ltmgr.tracklayout)
  doc.title = 'Training Panel'


def main():
  global survargs, wellnm, logs

  survargs = {'dtectdata': ['/home/olawale/'], 'survey': ['F3_Demo_2020']}

  server = Server({'/' : training_app})
  server.start()
  server.io_loop.add_callback(server.show, "/")
  server.io_loop.start()

if __name__ == "__main__":
    main()
