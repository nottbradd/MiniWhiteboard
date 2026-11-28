"""Record the official portable app on a disposable Windows runner."""
from pathlib import Path
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import win32api as api
import win32con as con
import win32gui as gui
import win32process
import win32ui
from PIL import Image, ImageChops

U = ctypes.WinDLL("user32", use_last_error=True)
U.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
BACKGROUND = "#dce5df"
CHORD = (con.VK_LCONTROL, con.VK_LWIN, con.VK_LSHIFT, ord("W"))
OUT = Path("verification/front-media")
SCALE = 1.5
ZIP_HASH = "f7340c841f7913b90c649693891cf76712ed6e2405e9b75cca28e51e2b4e11ef"
EXE_HASH = "39ff0141dc7ddd27c8f6da668bf5ceea1dedc4474f7e24ab3affb93ef5d33f16"


def geometry():
    w, h = api.GetSystemMetrics(0), api.GetSystemMetrics(1)
    bw, bh = round(422*SCALE), round(245*SCALE)
    left, top = (w-bw)//2, (h-bh)//2 + 28
    return (left, top), (left+bw, top+bh), (left-18, top-101, left+bw+18, top+bh+20)


def desktop():
    import tkinter as tk
    root = tk.Tk()
    root.title("Mini Whiteboard recording backdrop")
    root.overrideredirect(True)
    w,h = api.GetSystemMetrics(0),api.GetSystemMetrics(1)
    root.geometry(f"{w}x{h}+0+0")
    paper=tk.Canvas(root,bg=BACKGROUND,borderwidth=0,highlightthickness=0)
    paper.pack(fill="both",expand=True)
    start,end,_=geometry()
    cue=paper.create_text((start[0]+end[0])//2,start[1]-48,text="Ctrl + Win + Shift + W",
                          font=("Segoe UI",18),fill="#31493c",state="hidden")
    def read_keys():
        down=all(api.GetAsyncKeyState(k)&0x8000 for k in CHORD)
        paper.itemconfigure(cue,state="normal" if down else "hidden")
        root.after(20,read_keys)
    root.after(60,read_keys)
    root.mainloop()


def windows(pid, shown=True):
    result={}
    def each(handle, _extra):
        if win32process.GetWindowThreadProcessId(handle)[1]==pid and (not shown or gui.IsWindowVisible(handle)):
            result[gui.GetWindowText(handle)]=handle
        return True
    gui.EnumWindows(each,None)
    return result


def until(fn,label):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        value=fn()
        if value:return value
        time.sleep(.04)
    raise RuntimeError(label)


def move(point):
    api.SetCursorPos(tuple(round(v) for v in point))


def kd(key): api.keybd_event(key,0,0,0)
def ku(key): api.keybd_event(key,0,con.KEYEVENTF_KEYUP,0)
def tap(key):
    kd(key)
    time.sleep(.035)
    ku(key)
    time.sleep(.07)


def click(point):
    move(point);time.sleep(.05)
    api.mouse_event(con.MOUSEEVENTF_LEFTDOWN,0,0,0,0)
    time.sleep(.036)
    api.mouse_event(con.MOUSEEVENTF_LEFTUP,0,0,0,0)
    time.sleep(.085)


class Camera:
    """Capture compositor pixels and the actual Windows cursor at its hotspot."""
    def __init__(self, box):
        l,t,r,b=box
        self.box=box
        self.size=(r-l,b-t)
        self.handle=gui.GetDC(0)
        self.src=win32ui.CreateDCFromHandle(self.handle)
        self.memory=self.src.CreateCompatibleDC()
        self.bitmap=win32ui.CreateBitmap()
        self.bitmap.CreateCompatibleBitmap(self.src,*self.size)
        self.old=self.memory.SelectObject(self.bitmap)
        self.cursor_visible_frames=0
        self.cursor_recovered_frames=0
        self.arrow=gui.LoadCursor(0,con.IDC_ARROW)

    def capture(self, cursor):
        x,y=self.box[:2]
        self.memory.BitBlt((0,0),self.size,self.src,(x,y),con.SRCCOPY|0x40000000)
        if cursor:
            flags,handle,pt=gui.GetCursorInfo()
            if flags & 1 and handle:
                self.cursor_visible_frames+=1
            else:
                # A hosted desktop can suppress its hardware cursor. Composite the
                # system cursor at the measured OS position, as a screen recorder does.
                self.cursor_recovered_frames+=1
                handle=handle or self.arrow
                pt=api.GetCursorPos()
            _,hx,hy,mask,color=gui.GetIconInfo(handle)
            try:
                gui.DrawIconEx(self.memory.GetSafeHdc(),pt[0]-x-hx,pt[1]-y-hy,handle,
                               api.GetSystemMetrics(con.SM_CXCURSOR),api.GetSystemMetrics(con.SM_CYCURSOR),0,0,con.DI_NORMAL)
            finally:
                if mask:gui.DeleteObject(mask)
                if color:gui.DeleteObject(color)
        bits=self.bitmap.GetBitmapBits(True)
        return Image.frombytes("RGB",self.size,bits,"raw","BGRX",0,1)

    def close(self):
        self.memory.SelectObject(self.old)
        gui.DeleteObject(self.bitmap.GetHandle())
        self.memory.DeleteDC()
        gui.ReleaseDC(0,self.handle)


def bezier(start,*controls):
    points=[start]
    for a,b,end in zip(controls[::3],controls[1::3],controls[2::3]):
        origin=points[-1]
        length=sum(math.dist(i,j) for i,j in ((origin,a),(a,b),(b,end)))
        n=max(3,round(length/4))
        for k in range(1,n+1):
            t=k/n
            points.append(tuple((1-t)**3*origin[i]+3*(1-t)**2*t*a[i]+3*(1-t)*t*t*b[i]+t**3*end[i] for i in (0,1)))
    return points


def record(exe,archive):
    from PySide6.QtCore import QSettings
    OUT.mkdir(exist_ok=True,parents=True)
    assert os.environ.get("RUNNER_ENVIRONMENT")=="github-hosted"
    for f,h in ((exe,EXE_HASH),(archive,ZIP_HASH)):
        assert hashlib.sha256(f.read_bytes()).hexdigest()==h
    settings=QSettings("MiniWhiteboard","MiniWhiteboard")
    assert not settings.contains("shortcuts/custom_windows"),"Expected the release defaults"
    settings.setValue("appearance/theme","White")
    settings.setValue("tools/floating",True)
    settings.sync()
    start,end,crop=geometry()
    bg=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--backdrop"],creationflags=subprocess.CREATE_NO_WINDOW)
    proc=None;camera=None;held=[];frames=[];durations=[];stages=[]
    def frame(label,ms):
        im=camera.capture(True);frames.append(im);durations.append(ms);stages.append(label)
    def point(x,y):
        return (round(start[0]+x*SCALE),round(start[1]+y*SCALE))
    def stroke(pts,filmed=False):
        move(point(*pts[0]));time.sleep(.06)
        api.mouse_event(con.MOUSEEVENTF_LEFTDOWN,0,0,0,0)
        try:
            for i,pos in enumerate(pts[1:],1):
                move(point(*pos));time.sleep(.016 if filmed else .009)
                if filmed and i%3==0:
                    frame("drawing",50)
        finally:
            api.mouse_event(con.MOUSEEVENTF_LEFTUP,0,0,0,0)
        time.sleep(.09)
    def pencil(path):stroke(bezier(*path))
    def ink(n):
        tap(ord("C"));time.sleep(.12);tap(ord(str(n)));time.sleep(.16)
    def text(x,y,value,number):
        tap(ord("T"));tap(ord(str(number)));click(point(x,y));time.sleep(.14)
        for ch in value:
            code=api.VkKeyScan(ch)
            if code & 0x100:kd(con.VK_SHIFT)
            kd(code&255);ku(code&255)
            if code & 0x100:ku(con.VK_SHIFT)
            time.sleep(.012)
        kd(con.VK_CONTROL);tap(con.VK_RETURN);ku(con.VK_CONTROL);tap(con.VK_ESCAPE)
    try:
        backdrop=until(lambda:windows(bg.pid).get("Mini Whiteboard recording backdrop"),"Background did not open")
        # A controlled, quiet desktop stays behind the app and hides runner console windows.
        gui.SetWindowPos(backdrop,con.HWND_TOPMOST,0,0,0,0,con.SWP_NOMOVE|con.SWP_NOSIZE|con.SWP_SHOWWINDOW)
        click((start[0]+10,end[1]+10))
        env={**os.environ,"QT_SCALE_FACTOR":"1.5"}
        proc=subprocess.Popen([str(exe)],env=env,cwd=str(exe.parent))
        until(lambda:windows(proc.pid,False).get("QTrayIconMessageWindow"),"Frozen tray did not start")
        time.sleep(.45)
        camera=Camera(crop)
        move(start);time.sleep(.12)
        frame("start",300)
        assert ImageChops.difference(frames[-1],camera.capture(False)).getbbox(),"Missing recorded cursor at start"
        for k in CHORD:
            kd(k);held.append(k);time.sleep(.026)
        time.sleep(.23)
        assert all(api.GetAsyncKeyState(k)&0x8000 for k in CHORD)
        frame("holding",700)
        for i in range(1,23):
            t=i/22;f=t*t*(3-2*t)
            move((start[0]+(end[0]-start[0])*f,start[1]+(end[1]-start[1])*f))
            time.sleep(.043)
            frame("moving",50)
        frame("sized",360)
        assert "Whiteboard 1" not in windows(proc.pid),"Board created before release"
        for k in reversed(CHORD):
            ku(k);held.remove(k);time.sleep(.024)
        board=until(lambda:windows(proc.pid).get("Whiteboard 1"),"Default shortcut did not create board")
        toolbar=until(lambda:windows(proc.pid).get("Mini Whiteboard floating tools"),"Toolbar did not show")
        def in_app(pos):
            child=gui.WindowFromPoint(pos)
            return win32process.GetWindowThreadProcessId(child)[1]==proc.pid
        assert in_app(point(140,105)),"Board is covered"
        time.sleep(.19)
        frame("placed",420)
        # One continuous pen stroke outlines a leaf and finishes with its midrib.
        leaf=bezier((119,164),(133,112),(188,83),(286,56),
                    (271,110),(213,166),(119,164),(140,157),(192,113),(227,96))
        to=point(*leaf[0])
        for step in range(1,8):
            t=step/7
            move((end[0]+(to[0]-end[0])*t,end[1]+(to[1]-end[1])*t))
            time.sleep(.042);frame("approach",50)
        stroke(leaf,filmed=True)
        move(point(290,183));time.sleep(.14);frame("stroke complete",950)
        # The screenshot is a second board state created through normal drawing and text actions.
        kd(con.VK_CONTROL);tap(ord("Z"));ku(con.VK_CONTROL);time.sleep(.12)
        text(29,14,"Kitchen herbs",2)
        text(29,189,"Give mint its own pot.",1)
        tap(ord("D"));tap(ord("1"))
        # Wide planter with a folded lip and a separate, smaller pot.
        for path in [
          ((34,120),(67,119),(166,119),(244,118),(247,118),(248,123),(246,128),(186,130),(92,129),(34,130),(32,127),(32,122),(34,120)),
          ((39,131),(42,138),(46,157),(51,167),(81,170),(188,170),(229,166),(234,154),(238,138),(240,130)),
          ((293,121),(309,119),(352,119),(375,120),(378,120),(378,126),(375,128),(351,130),(314,130),(293,129),(291,127),(292,122),(293,121)),
          ((299,130),(302,142),(307,158),(311,168),(324,171),(347,171),(360,168),(365,157),(370,141),(372,130))
        ]:pencil(path)
        ink(4)
        # Two herb cuttings in the bed and a leafier mint sprig in its own pot.
        def sprig(x,y,size,lean):
            def local(p):return (x+(p[0]+lean*(-p[1]))*size,y+p[1]*size)
            paths=[
               ((0,0),(-2,-16),(0,-35),(5,-56)),
               ((0,-14),(-14,-13),(-25,-24),(-28,-35),(-14,-35),(-4,-30),(0,-17)),
               ((1,-27),(6,-41),(17,-47),(28,-46),(26,-33),(14,-25),(1,-24)),
               ((3,-40),(-7,-43),(-15,-54),(-15,-63),(-3,-61),(2,-52),(4,-44)),
               ((5,-54),(5,-66),(13,-72),(19,-75),(20,-63),(13,-57),(5,-54))]
            for chain in paths:pencil(tuple(local(p) for p in chain))
        sprig(89,118,.76,-.12);sprig(177,118,.88,.05);sprig(333,120,.91,-.08)
        # Return to Draw. Settle tooltip/feedback and keep the pointer outside the photo.
        move((crop[0]-12,crop[1]+20));time.sleep(2.2)
        assert gui.GetForegroundWindow()==board
        assert all(in_app(p) for p in (point(26,24),point(386,151)))
        hero=camera.capture(False)
        hero.save(OUT/"windows-herb-sketch-v136.png",optimize=True)
        # A shared palette covers the display colours of all phases without a synthetic overlay.
        thumb=Image.new("RGB",(180,len(frames)*100))
        for i,im in enumerate(frames):thumb.paste(im.resize((180,100)),(0,i*100))
        pal=thumb.quantize(colors=256,method=Image.Quantize.MEDIANCUT)
        indexed=[im.quantize(palette=pal,dither=Image.Dither.NONE) for im in frames]
        indexed[0].save(OUT/"windows-hold-place-draw-v136.gif",save_all=True,append_images=indexed[1:],
                        duration=durations,loop=0,optimize=True,disposal=1)
        for label in ("start","holding","sized","placed","stroke complete"):
            idx=stages.index(label);frames[idx].save(OUT/(label.replace(" ","-")+".png"))
        frames[stages.index("moving")+12].save(OUT/"drag-in-progress.png")
        print("Saved",len(frames),"frames",flush=True)
        (OUT/"receipt.json").write_text(json.dumps(dict(release="v1.3.6",zip_sha256=ZIP_HASH,exe_sha256=EXE_HASH,
            process=proc.pid,board=gui.GetWindowRect(board),toolbar=gui.GetWindowRect(toolbar),crop=crop,
            chord="Ctrl+Win+Shift+W",before_release_no_board=True,after_release_board_visible=True,
            stages=stages,durations=durations,windows_build=sys.getwindowsversion().build,
            cursor_native_frames=camera.cursor_visible_frames,cursor_composited_frames=camera.cursor_recovered_frames),indent=2))
    except Exception:
        if camera:camera.capture(False).save(OUT/"failure.png")
        if proc:print("Window titles", list(windows(proc.pid,False)),flush=True)
        raise
    finally:
        for k in reversed(held):ku(k)
        api.mouse_event(con.MOUSEEVENTF_LEFTUP,0,0,0,0)
        if camera:camera.close()
        for p in (proc,bg):
            if p and p.poll() is None:p.terminate();p.wait(6)


if __name__=="__main__":
    if sys.argv[1]=="--backdrop":desktop()
    else:record(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
