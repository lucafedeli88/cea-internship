"""
Util functions
"""

from paraview.simple import *

import sys, os, pickle
__DIR__ = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(__DIR__, ".."))

import config
from importlib import reload
reload(config)

from config import *

def getView(source,
            COLOR="Cool to Warm (Extended)",
            OPACITY=1.0,
            CLIM=1,
            THRESHOLD=0.2,
            animated=False):
    """
    Configure and return a ParaView view
    """
    view = CreateRenderView()
    displayProperties = Show(source, view=view)

    ColorBy(displayProperties, ("CELLS", "By"))

    # Color table
    byLUT = GetColorTransferFunction('By', displayProperties, separate=True)
    byLUT.ApplyPreset(COLOR)
    byLUT.RescaleTransferFunction([-CLIM, CLIM])
    byLUT.AutomaticRescaleRangeMode = 'Never'

    # Opacity map
    byPWF = GetOpacityTransferFunction('By', displayProperties, separate=True)
    byPWF.Points = [
        # format: val, opacity, 0.5, 0.0 (last 2?!)
        -CLIM,      OPACITY, 0.5, 0.,
        -THRESHOLD, OPACITY, 0.5, 0.,
        -THRESHOLD, 0.,      0.5, 0.,
        THRESHOLD,  0.,      0.5, 0.,
        THRESHOLD,  OPACITY, 0.5, 0.,
        CLIM,       OPACITY, 0.5, 0.,
    ]
    byPWF.ScalarRangeInitialized = 1
    
    # Display properties
    displayProperties.Representation = 'Volume'
    
    # Color
    displayProperties.ColorArrayName = 'By'
    displayProperties.LookupTable = byLUT
    
    # Opacity
    displayProperties.OpacityArrayName = 'By'
    displayProperties.ScalarOpacityFunction = byPWF

    # Separate color map
    displayProperties.UseSeparateColorMap = True

    scalarBar = GetScalarBar(byLUT, view)
    scalarBar.Title = 'By'
    scalarBar.ComponentTitle = ''
    scalarBar.Visibility = 1
    displayProperties.SetScalarBarVisibility(view, True)

    if animated:
        # Setup animation scene
        animationScene = GetAnimationScene()
        animationScene.PlayMode = 'Snap To TimeSteps'

    # Configure view
    view.ViewSize = [945, 880]
    view.AxesGrid = 'GridAxes3DActor'

    # Configure camera
    view.CenterOfRotation = GetActiveCamera().GetFocalPoint()
    #view.CameraPosition = [38.508498092504716, 6.2875904189648475, 22.242265004619007]
    #view.CameraFocalPoint = [7.670000000000014, 7.290000000000007, 11.399999999999999]
    #view.CameraViewUp = [-0.014939444962305284, -0.9986456446556182, -0.04983662703858452]
    return view


def getSource(CLIP_HALF=False,
              CLIP_QUARTER=False,
              CLIP_INV_QUARTER=False,
              LOG_SCALE=False,
              LOG_THRESHOLD=5e-5,
              SUFFIX="",
              *kwargs):
    """
    Returns a programmable source that automatically imports image files.
    """
    # https://docs.paraview.org/en/latest/ReferenceManual/pythonProgrammableFilter.html#programmable-filter

    if len(list(x for x in [CLIP_HALF, CLIP_QUARTER, CLIP_INV_QUARTER] if x)) >= 2:
        raise ValueError("Cannot stack CLIPs !")

    HEADER = """
### GENERATED HEADER ###
import os, pickle

def get_path(x, folder=""):
    return os.path.abspath(os.path.join("%s", folder, x))

# Build-specific config
PROPAGATION_TYPE = "%s"
TOT_Z = %s
T_STEPS = %s
X_STEPS = pickle.loads(%s)
Y_STEPS = pickle.loads(%s)
Z_STEPS = pickle.loads(%s)
Z_LENGTH = %s
dt = %s
dz = %s
x_drop = %s
y_drop = %s
z_drop = %s
### END OF HEADER ###
    """.strip() % (
        STORAGE_FOLDER,
        #
        PROPAGATION_TYPE,
        TOT_Z,
        T_STEPS,
        pickle.dumps(X_STEPS),
        pickle.dumps(Y_STEPS),
        pickle.dumps(Z_STEPS),
        Z_LENGTH,
        dt,
        dz,
        x_drop,
        y_drop,
        z_drop,
    )
    
    CONFIG_HDR = """
###### CONFIG ######
# User configurable
self.MAX_INSTANT = %s
self.CLIP_HALF = %s
self.CLIP_QUARTER = %s
self.CLIP_INV_QUARTER = %s
self.LOG_SCALE = %s
self.LOG_THRESHOLD = %s
self.SUFFIX = "%s"
    """.strip() % (
        MAX_INSTANT,
        CLIP_HALF,
        CLIP_QUARTER,
        CLIP_INV_QUARTER,
        LOG_SCALE,
        LOG_THRESHOLD,
        SUFFIX,
    )
    
    source = ProgrammableSource(registrationName='AnimatedLaserBeam')
    source.OutputDataSetType = 'vtkImageData'
    with open(os.path.join(__DIR__, 'internal', 'script.py')) as fd:
        source.Script = "\n".join([HEADER, fd.read()])
    with open(os.path.join(__DIR__, 'internal', 'reqscript.py')) as fd:
        source.ScriptRequestInformation = "\n".join([CONFIG_HDR, HEADER, fd.read()])

    # Trigger RequestInformation
    source.UpdatePipelineInformation()
    
    paraview.simple._DisableFirstRenderCameraReset()
    getView(source, animated=True, *kwargs)

    return source