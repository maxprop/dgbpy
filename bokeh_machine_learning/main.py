#__________________________________________________________________________
#
# (C) dGB Beheer B.V.; (LICENSE) http://opendtect.org/OpendTect_license.txt
# Author:        A. Huck
# Date:          Jan 2019
#
# _________________________________________________________________________

import os
import sys
import argparse
from dgbpy.bokehserver import StartBokehServer, DefineBokehArguments

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
traingrp.add_argument( '--transfer', dest='transfer',
            action='store_true', default=False,
            help='Do transfer training' )
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

import odpy.common as odcommon
odcommon.initLogging( args )
odcommon.proclog_logger.setLevel( 'DEBUG' )

import dgbpy.servicemgr as dgbservmgr


def training_app(doc):
# Keep all lengthy operations below
  import logging
  logging.getLogger('bokeh.bokeh_machine_learning.main').setLevel(logging.DEBUG)
  odcommon.proclog_logger = logging.getLogger('bokeh.bokeh_machine_learning.main')
  
  odcommon.log_msg( 'Start training UI')
  
  from os import path
  import psutil
  from functools import partial

  from bokeh.io import curdoc
  from bokeh.layouts import column
  from bokeh.models.widgets import Panel, Select, Tabs, TextInput

  from odpy.oscommand import (getPythonCommand, execCommand, kill,
                            isRunning, pauseProcess, resumeProcess)
  import dgbpy.keystr as dgbkeys
  from dgbpy import mlapply as dgbmlapply
  from dgbpy import uibokeh, uikeras, uisklearn
  from dgbpy import mlio as dgbmlio

  examplefilenm = args['h5file'].name
  trainingcb = None
  traintype =  dgbmlapply.TrainType.New
  doabort = False
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

    trainpanel = Panel(title=traintabnm)
    parameterspanel = Panel(title=paramtabnm)
    mainpanel = Tabs(tabs=[trainpanel,parameterspanel])

    ML_PLFS = []
    ML_PLFS.append( uikeras.getPlatformNm(True) )
    ML_PLFS.append( uisklearn.getPlatformNm(True) )

    platformfld = Select(title="Machine learning platform:",options=ML_PLFS)
    platformparsbut = uibokeh.getButton(paramtabnm,\
      callback_fn=partial(uibokeh.setTabFromButton,panelnm=mainpanel,tabnm=paramtabnm))

    info = None
    keraspars = None
    sklearnpars = None
    parsgroups = None
    traininglogfilenm = None

    def makeUI(examplefilenm):
      nonlocal info
      nonlocal keraspars
      nonlocal sklearnpars
      nonlocal parsgroups
      info = dgbmlio.getInfo( examplefilenm, quick=True )
      uikeras.info = info
      keraspars = uikeras.getUiPars()
      sklearnpars = uisklearn.getUiPars( info[dgbkeys.classdictstr] )
      parsgroups = (keraspars,sklearnpars)

    def updateUI():
      nonlocal info
      nonlocal keraspars
      keraspars['uiobjects']['dodecimatefld'].active = []
      keraspars['uiobjects']['sizefld'].text = uikeras.getSizeStr(info[dgbkeys.estimatedsizedictstr])

    makeUI(examplefilenm)
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
          if val == dgbmlapply.TrainType.New.name:
            traintype = dgbmlapply.TrainType.New
            model = None
          elif val == dgbmlapply.TrainType.Resume.name:
            traintype = dgbmlapply.TrainType.Resume
          elif val == dgbmlapply.TrainType.Transfer.name:
            traintype = dgbmlapply.TrainType.Transfer
        elif key=='Input Model File':
          if os.path.isfile(val):
            model = val
          else:
            model = None
            traintype = dgbmlapply.TrainType.New
        elif key=='ProcLog File':
          traininglogfilenm = val
        elif key=='Output Model File':
          doRun( doTrain(val) )
        elif key=='Examples File':
          if examplefilenm != val:
            examplefilenm = val
            info = dgbmlio.getInfo( examplefilenm, quick=True )
            uikeras.info = info
            doc.add_next_tick_callback(partial(updateUI))
      return dict()
     
    this_service.addAction('BokehParChg', procArgChgCB )
      
    def mlchgCB( attrnm, old, new):
      selParsGrp( new )

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
      parameterspanel.child = column( parsgrp, parsbackbut )
      doc.add_root(mainpanel)
      dgbservmgr.Message().sendObjectToAddress(
                 args['bsmserver'],
                 'ml_training_msg',
                 {'platform_change': platformnm,
                  'bokehid': args['bokehid']
                 })

    def getUiParams():
      parsgrp = getParsGrp( platformfld.value )
      if platformfld.value == uikeras.getPlatformNm():
        return uikeras.getUiParams( keraspars )
      elif platformfld.value == uisklearn.getPlatformNm():
        return uisklearn.getUiParams( sklearnpars )
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
      dict.update({dgbkeys.learntypedictstr: traintype.name})
      return ret

    def doRun( cb = None ):
      nonlocal trainingcb
      nonlocal doabort
      doabort = False
      if cb == None:
        dgbservmgr.Message().sendObjectToAddress( args['bsmserver'],
                             'ml_training_msg',
                             {'training can start request': '',
                             'bokehid': args['bokehid']
                             })
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
      
      modelnm = trainedfnm
      scriptargs = getProcArgs( platformfld.value, getUiParams(), \
                                modelnm )
      cmdtorun = getPythonCommand( trainscriptfp, scriptargs['posargs'], \
                              scriptargs['dict'], scriptargs['odargs'] )
      dgbservmgr.Message().sendObjectToAddress(
                 args['bsmserver'],
                 'ml_training_msg',
                 {'training_started': '',
                  'bokehid': args['bokehid']
                 })

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
          dgbservmgr.Message().sendObjectToAddress(
                     args['bsmserver'],
                     'ml_training_msg',
                     {
                       'training_finished': '',
                       'bokehid': args['bokehid']
                     })
        rectrainingcb[uibokeh.timerkey] = None
        trainingcb[uibokeh.timerkey] = None
        return (False,rectrainingcb)
      return (True,rectrainingcb)

    platformfld.on_change('value',mlchgCB)
    buttonsgrp = uibokeh.getRunButtonsBar( doRun, doAbort, doPause, doResume, trainMonitorCB )
    trainpanel.child = column( platformfld, platformparsbut, buttonsgrp )

    def initWin():
      mllearntype = info[dgbkeys.learntypedictstr]
      if mllearntype == dgbkeys.loglogtypestr or \
        mllearntype == dgbkeys.seisproptypestr:
        platformfld.value = uisklearn.getPlatformNm(True)[0]
      else:
        platformfld.value = uikeras.getPlatformNm(True)[0]
      mlchgCB( 'value', 0, platformfld.value )
      doc.title = 'Machine Learning'

    initWin()
  
StartBokehServer({'/': training_app}, args)
