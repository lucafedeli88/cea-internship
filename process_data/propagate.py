"""
Propagate the data
"""

from common import *

# Check args

parser = argparse.ArgumentParser(description='Process numpy files to create frames')
parser.add_argument('--filter-lowpass', type=float, nargs=1,
                    help='Applies a low-pass filter to a frequence')
parser.add_argument('--filter-highpass', type=float, nargs=1,
                    help='Applies a low-pass filter to a frequence')
parser.add_argument('--suffix', type=str, nargs=1,
                    help='Add suffix to file names')
args = parser.parse_args()

print("""
  _____                                   _   _
 |  __ \                                 | | (_)
 | |__) | __ ___  _ __   __ _  __ _  __ _| |_ _ _ __   __ _
 |  ___/ '__/ _ \| '_ \ / _` |/ _` |/ _` | __| | '_ \ / _` |
 | |   | | | (_) | |_) | (_| | (_| | (_| | |_| | | | | (_| |_ _ _
 |_|   |_|  \___/| .__/ \__,_|\__, |\__,_|\__|_|_| |_|\__, (_|_|_)
                 | |           __/ |                   __/ |
                 |_|          |___/                   |___/
-------------------------------------------------------------------
""")

print("PROPAGATION TYPE: %s - DATA INPUT: %s" % (PROPAGATION_TYPE, DATA_FORMAT))
if args.filter_lowpass or args.filter_highpass:
    print("FILTER: %s, fc=%s" % (args.filter_lowpass and "lowpass" or "highpass",
                                (args.filter_lowpass or args.filter_highpass)[0]))

# Load files
print("Loading field...", end="", flush=True)
if PROPAGATION_TYPE == "z":
    by = np.load(get_path('By.npy', "npy_files"))
elif PROPAGATION_TYPE == "t":
    by = np.load(get_path('By_xyz.npy', "npy_files"))
    by = by.transpose(
        DATA_FORMAT.index("X"),
        DATA_FORMAT.index("Y"),
        DATA_FORMAT.index("Z"),
    )
print("OK")

if SUBSAMPLE_IN_PROPAGATE:
    print("Subsampling plane...", end="", flush=True)
    by = by[::x_subsampling, ::y_subsampling, ::]
    print("OK")

# Crop
if any(x for x in [x_min, x_max, y_min, y_max, z_min, z_max] if x is not None):
    print("Crop field...", end="", flush=True)
    by = by[x_min:x_max,y_min:y_max,z_min:z_max]
    print("OK")

infos(by)

print("Moving data to GPU...", end="", flush=True)
by = cp.asarray(by, dtype="complex64")
print("OK")

if ROTATION_ANGLE:
    print("Rotating by %s°...", end="", flush=True)
    cpx.scipy.ndimage.rotate(by,
                             ROTATION_ANGLE,
                             reshape=False,
                             output=by,
                             mode="constant",
                             cval=0.0)
    print("OK")

# Perform calculations

if PROPAGATION_TYPE == "z":
    KX, KY, W = build_grid(X_STEPS, Y_STEPS, T_STEPS)
elif PROPAGATION_TYPE == "t":
    # Re-build Z axis but with Z_LENGTH points over TOT_Z
    TOT_Z = TOT_Z or (Z_STEPS[0] - Z_STEPS[-1])
    Z_LENGTH = Z_LENGTH or Z_STEPS.shape[0]
    z = np.arange(TOT_Z, 0, abs(TOT_Z / Z_LENGTH))
    # (we could technically use Z_STEPS instead of z)
    KX, KY, KZ = build_grid(X_STEPS, Y_STEPS, z)
    print("Build W...", end="", flush=True)
    W = np.sqrt(KX**2 + KY**2 + KZ**2)
    print("OK")

byfft = by
build_fft_inplace(byfft)
del by

aW = np.abs(W)
Wni = (aW <= 0.01)  # Do not try to divide by 0
# Check for filter
if args.filter_lowpass:
    fl = args.filter_lowpass[0]
    Wni = Wni | (aW > fl)
if args.filter_highpass:
    fl = args.filter_highpass[0]
    Wni = Wni | (aW < fl)

if FILTER_OUT_LOW_FREQ:
    Wni = Wni | (aW < FILTER_OUT_LOW_FREQ)
del aW


# Propagate

print("Building propagation vector (slow).", end="", flush=True)

# See PROPAGATION_DEMO.md for explanation of this formula

propag = np.zeros(byfft.shape, dtype="complex64")
# Create propag vector
if PROPAGATION_TYPE == "z":
    Wi = np.asarray(1 - Wni, dtype="bool")
    propag[Wi] = np.exp(-np.pi * 1j * (KX[Wi]**2 + KY[Wi]**2) * dz / W[Wi])
    propag[Wni] = 0.
elif PROPAGATION_TYPE == "t":
    propag = np.exp(-np.pi * 2j * (W - KZ) * dt)
    propag[KZ < 0] = 0.
    propag[Wni] = 0.
del Wni
print(".", end="", flush=True)
print("OK")

print("Copying propagation vector to GPU...", end="", flush=True)
propag = cp.asarray(propag,
                    dtype="complex64")
print("OK")

dirpath = get_path("", "frames")
if not os.path.exists(dirpath):
    os.mkdir(dirpath)

suffix = args.suffix and args.suffix[0] or ""

if PROPAGATION_TYPE == "z":
    # Propagate on z
    prog = tqdm(range(MAX_INSTANT))
    prog.set_description("Propagating on z")
    for i in prog:
        byfft *= propag
        v = cpx.scipy.fft.ifftn(byfft,
                                axes=(0,1,2))
        frame = cp.real(
            v[::x_drop, ::y_drop, :t.shape[0]]
        ).get()
        np.savez(get_path("f%s%s.npz" % (i, suffix), "frames"), frame=frame)
        del v
elif PROPAGATION_TYPE == "t":
    # First propagate on t
    prog = tqdm(range(MAX_INSTANT))
    prog.set_description("Propagating on t")
    for i in prog:
        byfft *= propag
        v = cpx.scipy.fft.ifftn(byfft,
                                axes=(0,1,2))
        np.savez(
            get_path("f%s%s.npz" % (i, suffix), "frames"),
            frame=cp.real(
                v[::x_drop, ::y_drop, ::z_drop]
            ).get()
        )
        del v

print("done")
