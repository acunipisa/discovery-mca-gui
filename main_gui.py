import os
import psutil

from frontends.gui_app import main

if __name__ == "__main__":
    p = psutil.Process(os.getpid())
    p.nice(psutil.REALTIME_PRIORITY_CLASS)
    main()
