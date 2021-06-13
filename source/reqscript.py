"""
The 'RequestInformation Script' parameter of a ProgrammableSource
"""

# https://docs.paraview.org/en/latest/ReferenceManual/pythonProgrammableFilter.html#programmable-filter

import os
import numpy as np
import cupy as cp
import cupyx as cpx

import paraview.util

# Some consts
c = 299792458

# Configure output
executive = self.GetExecutive()
outInfo = executive.GetOutputInformation(0)

# Load files
print("Loading files...")
self.by = np.load(get_path('By.npy'))
self.x = np.load(get_path('x.npy'))
self.y = np.load(get_path('y.npy'))
self.t = np.load(get_path('t.npy'))
print("Files loaded!")

self.x, self.y = self.y, self.x

# Apply discrete fourier transform
print("Moving data to GPU. Allocation array: %s" % str(self.by.shape))
self.byfft = cp.asarray(self.by, dtype="complex64")
print("Applying fourier transform...")
self.byfft = cpx.scipy.fft.fftn(self.byfft,
                                axes=(0,1,2),
                                norm="forward",
                                overwrite_x=True)

print("OK!")

# print("Debug")
# print(self.by.shape)
# print(self.x.shape)
# print(self.y.shape)
# print(self.t.shape)

# Define Z axis (arbitrary)
self.zlength = 30
self.dz = 1 / self.zlength

# Build frequences grid
freqx = np.fft.fftfreq(self.x.size, d=self.x[1] - self.x[0])
freqy = np.fft.fftfreq(self.y.size, d=self.y[1] - self.y[0])
freqt = np.fft.fftfreq(self.t.size, d=self.t[1] - self.t[0])
self.FY, self.FX, self.FT = np.meshgrid(freqy, freqx, freqt, indexing='ij')

self.data = []

# Propagate
print("Propagating...")
# data = data * np.exp(-np.pi * 1j * (self.FX**2 + self.FY**2) * self.dz / self.FT)
for i in range(self.zlength):
    self.byfft *= np.exp(-np.pi * 1j * self.FT * self.dz / c)
    v = cupyx.scipy.fftpack.ifftn(self.byfft, axes=(0,1,2), norm="backward")
    
    

print(self.FT)

## Define re-usable grid
#X, Y, Z = np.meshgrid(self.x, self.y, self.z)
#self.points = algs.make_vector(X.ravel(),
#                               Y.ravel(),
#                               Z.ravel())

# Set boundaries
outInfo.Set(executive.WHOLE_EXTENT(),
    # (xmin, xmax, ymin, ymax, zmin, zmax)
    0, self.x.shape[0] - 1,
    0, self.y.shape[0] - 1,
    0, self.length - 1
)
outInfo.Set(vtk.vtkDataObject.SPACING(),
    # (dx, dy, dz)
    self.x[1] - self.x[0],
    self.y[1] - self.y[0],
    self.dz,
)

# Set time steps
outInfo.Remove(executive.TIME_STEPS())
for timestep in self.t:
    outInfo.Append(executive.TIME_STEPS(), timestep)

outInfo.Remove(executive.TIME_RANGE())
outInfo.Append(executive.TIME_RANGE(), self.t[0])
outInfo.Append(executive.TIME_RANGE(), self.t[-1])
