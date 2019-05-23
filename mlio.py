#__________________________________________________________________________
#
# (C) dGB Beheer B.V.; (LICENSE) http://opendtect.org/OpendTect_license.txt
# Author:        A. Huck
# Date:          Nov 2018
#
# _________________________________________________________________________
# various tools machine learning data handling
#


import odpy.dbman as oddbman
import dgbpy.keystr as dgbkeys
import dgbpy.hdf5 as dgbhdf5

nladbdirid = '100060'
mltrlgrp = 'Deep Learning Model'
kerastrl = 'Keras'

def getInfo( filenm ):
  return dgbhdf5.getInfo( filenm )

def getTrainingData( filenm, decim=False ):
  examples = dgbhdf5.getAllCubeLets( filenm, decim )
  info = getClasses( getInfo(filenm), examples )
  ret = { dgbkeys.infodictstr: info }
  for ex in examples:
    ret.update({ex: examples[ex]})
  if dgbkeys.classesdictstr in info and dgbkeys.ytraindictstr in examples:
    normalize_class_vector( examples[dgbkeys.ytraindictstr], \
                            info[dgbkeys.classesdictstr] )
  return ret

def getClasses( info, examples ):
  if not info[dgbkeys.classdictstr] or dgbkeys.classesdictstr in info:
    return info
  import numpy as np
  y_vec = examples[dgbkeys.ytraindictstr]
  classes = []
  (minval,maxval) = ( np.min(y_vec), np.max(y_vec) )
  for idx in np.arange(minval,maxval+1,1,dtype=np.uint8):
    if np.any(y_vec == idx ):
      classes.append( idx )
  if len(classes) > 0:
    info.update( {dgbkeys.classesdictstr: np.array(classes,dtype=np.uint8)} )
  return info

def normalize_class_vector( arr, classes ):
  import numpy as np
  classes = np.sort( classes )
  for i in range( len(classes) ):
    arr[arr == classes[i]] = i

def unnormalize_class_vector( arr, classes ):
  import numpy as np
  classes = np.sort( classes )
  for i in reversed(range( len(classes) ) ):
    arr[arr == i] = classes[i]

def getModel( modelfnm ):
  infos = dgbhdf5.getInfo( modelfnm )
  platform = infos[dgbhdf5.plfdictstr]
  if platform == dgbkeys.kerasplfnm:
    import dgbpy.dgbkeras as dgbkeras
    model = dgbkeras.load( modelfnm )
  elif platform == dgbkeys.scikitplfnm:
    log_msg( 'scikit platform not supported (yet)' )
    import dgbpy.dgbscikit as dgbscikit
    raise AttributeError
  else:
    log_msg( 'Unsupported machine learning platform' )
    raise AttributeError
  return (model,infos)

def getApplyInfoFromFile( modelfnm, outsubsel=None ):
  return getApplyInfo( dgbhdf5.getInfo(modelfnm), outsubsel )

def getApplyInfo( infos, outsubsel=None ):
  isclassification = infos[dgbhdf5.classdictstr]
  withclass = isclassification and \
              (outsubsel==None or dgbhdf5.classvalstr in outsubsel)
  withconfidence = isclassification and \
              (outsubsel==None or dgbhdf5.confvalstr in outsubsel)
  if isclassification:
    withprobs = dgbhdf5.getClassIndices( infos, outsubsel )
  else:
    withprobs = []
  return {
    dgbkeys.classdictstr: isclassification,
    dgbkeys.withclass: withclass,
    dgbkeys.withconfidence: withconfidence,
    dgbkeys.withprobs: withprobs
  }

def getSaveLoc( outnm, args ):
  dblist = oddbman.getDBList(mltrlgrp,args)
  try:
    dbkey = oddbman.getDBKeyForName( dblist, outnm )
  except ValueError:
    return oddbman.getNewEntryFileName(outnm,nladbdirid,mltrlgrp,kerastrl,\
                                       dgbhdf5.hdf5ext,args)
  return oddbman.getFileLocation( dbkey, args )
