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
args = parser.parse_args()

print("""
  _____                                   _   _
 |  __ \                                 | | (_)
 | |__) | __ ___  _ __   __ _  __ _  __ _| |_ _ _ __   __ _
 |  ___/ '__/ _ \| '_ \ / _` |/ _` |/ _` | __| | '_ \ / _` |
 | |   | | | (_) | |_) | (_| | (_| | (_| | |_| | | | | (_| |
 |_|   |_|  \___/| .__/ \__,_|\__, |\__,_|\__|_|_| |_|\__, (_|_|_)
                 | |           __/ |                   __/ |
                 |_|          |___/                   |___/
-------------------------------------------------------------------
""")

print("PROPAGATION TYPE: %s" % PROPAGATION_TYPE)
if args.filter_lowpass or args.filter_highpass:
    print("FILTER: %s, fc=%s" % (args.filter_lowpass and "lowpass" or "highpass",
                                (args.filter_lowpass or args.filter_highpass)[0]))

# Load files
print("Loading files...", end="", flush=True)
x = np.load(get_path('x.npy', "npy_files"))
y = np.load(get_path('y.npy', "npy_files"))
t = np.load(get_path('t.npy', "npy_files"))
if PROPAGATION_TYPE == "z":
    by = np.load(get_path('By.npy', "npy_files"))
    Z_LENGTH = t.shape[0]
elif PROPAGATION_TYPE == "t":
    by = np.load(get_path('By_xyz.npy', "npy_files"))
    #if Z_LENGTH is not None and t.shape[0] // z_drop < Z_LENGTH:
    #    print("Error: z_drop is too high compared to Z_LENGTH")
    #    import sys
    #    sys.exit(1)
print("OK")

z = np.arange(TOT_Z, 0, abs(TOT_Z / Z_LENGTH))
KY, KX, KZ, byfft = build_fft(x, y, z, by)

W = np.sqrt(KX**2 + KY**2 + KZ**2)

aW = np.abs(W)
Wi, Wni = (aW > 0.01), (aW <= 0.01)  # Do not try to divide by 0
# Check for filter
if args.filter_lowpass:
    fl = args.filter_lowpass[0]
    Wi = Wi & (aW <= fl)
    Wni = Wni | (aW > fl)
if args.filter_highpass:
    fl = args.filter_highpass[0]
    Wi = Wi & (aW >= fl)
    Wni = Wni | (aW < fl)
del aW

# Propagate

print("Building propagation vector (slow).", end="", flush=True)

# See PROPAGATION_DEMO.md for explanation of this formula

propag = np.zeros(by.shape, dtype="complex64")
# Create propag vector
if PROPAGATION_TYPE == "z":
    propag[Wi] = np.exp(-np.pi * 1j * (KX[Wi]**2 + KY[Wi]**2) * dz / W[Wi])
    propag[Wni] = 0.
elif PROPAGATION_TYPE == "t":
    propag = np.exp(-np.pi * 2j * W * dt)
    propag[KZ < 0] = 0.
print(".", end="", flush=True)
print("OK")

print("Copying propagation vector to GPU...", end="", flush=True)
propag = cp.asarray(propag,
                    dtype="complex64")
print("OK")

dirpath = get_path("", "frames")
if not os.path.exists(dirpath):
    os.mkdir(dirpath)

if PROPAGATION_TYPE == "z":
    prog = tqdm(range(MAX_INSTANT))
    prog.set_description("Propagating on z")
    for i in prog:
        byfft *= propag
        v = cpx.scipy.fft.ifftn(byfft,
                                axes=(0,1,2))
        frame = cp.real(
            v[::y_drop, ::x_drop, :t.shape[0]]
        ).transpose(1, 0, 2).get()
        np.savez(get_path("f%s.npz" % i, "frames"), frame=frame)
        del v
elif PROPAGATION_TYPE == "t":
    # First propagate on z
    prog = tqdm(range(MAX_INSTANT))
    prog.set_description("Propagating on t")
    for i in prog:
        byfft *= propag
        v = cpx.scipy.fft.ifftn(byfft,
                                axes=(0,1,2))
        np.savez(
            get_path("f%s.npz" % i, "frames"),
            frame=cp.real(
                v[::y_drop, ::x_drop, :Z_LENGTH]
            ).transpose(1, 0, 2).get()
        )
        del v

print("done")
