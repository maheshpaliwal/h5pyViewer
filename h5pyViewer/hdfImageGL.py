#!/usr/bin/env python
#*-----------------------------------------------------------------------*
#|                                                                       |
#|  Copyright (c) 2013 by Paul Scherrer Institute (http://www.psi.ch)    |
#|                                                                       |
#|              Author Thierry Zamofing (thierry.zamofing@psi.ch)        |
#*-----------------------------------------------------------------------*
'''
implements an image view to show a colored image of a hdf5 dataset.
'''

if __name__ == '__main__':
    #Used to guarantee to use at least Wx2.8
  import wxversion
  wxversion.ensureMinimal('2.8')
import wx
import os,h5py
import numpy as np
import utilities as ut

try:
  import glumpy
  from glumpy.graphics import VertexBuffer
  import wx.glcanvas
  from OpenGL.GL import *
except ImportError as e:
  print 'ImportError: '+e.message

def MplAddColormap(m,lut):
  if type(lut)==dict:
    try:
      lstR=lut['red']
      lstG=lut['green']
      lstB=lut['blue']
      kR,vR,dummy=zip(*lstR)
      kG,vG,dummy=zip(*lstG)
      kB,vB,dummy=zip(*lstB)
    except TypeError as e:
      print 'failed to add '+m+' (probably some lambda function)'
      #print lut
      return
    kLst=set()
    kLst.update(kR)
    kLst.update(kG)
    kLst.update(kB)
    kLst=sorted(kLst)
    vRGB=zip(np.interp(kLst, kR, vR),np.interp(kLst, kG, vG),np.interp(kLst, kB, vB))
    lut2=zip(kLst,vRGB)
  else:
    if type(lut[0][1])==tuple:
      lut2=lut
    else:
      kLst=np.linspace(0., 1., num=len(lut))
      lut2=zip(kLst,lut)
  
  #cmap = Colormap('gray',(0., (0.,0.,0.,1.)),(1., (1.,1.,1.,1.)))
  cm2=glumpy.colormap.Colormap(m,*tuple(lut2))
  setattr(glumpy.colormap,m,cm2)  
  
def MplAddAllColormaps():
  try:
    import matplotlib.cm as cm
  except ImportError as e:
    print 'ImportError: '+e.message
  maps=[m for m in cm.datad if not m.endswith("_r")]
  for m in maps:
    lut= cm.datad[m]
    MplAddColormap(m,lut)
  pass 

class GLCanvasImg(wx.glcanvas.GLCanvas):
  """A simple class for using OpenGL with wxPython."""
  def __init__(self,parent,SetStatusCB=None):
    if SetStatusCB:
      self.SetStatusCB=SetStatusCB
    self.GLinitialized = False
    attribList = (wx.glcanvas.WX_GL_RGBA,  # RGBA
                  wx.glcanvas.WX_GL_DOUBLEBUFFER,  # Double Buffered
                  wx.glcanvas.WX_GL_DEPTH_SIZE, 24)  # 24 bit

    # Create the canvas
    #self.canvas = wx.glcanvas.GLCanvas(parent, attribList=attribList)
    wx.glcanvas.GLCanvas.__init__(self, parent, attribList=attribList)

    # Set the event handlers.
    self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
    self.Bind(wx.EVT_SIZE, self.OnSize)
    self.Bind(wx.EVT_PAINT, self.OnPaint)
    self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWeel)
    self.Bind(wx.EVT_MOTION, self.OnMouseEvent)
    self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseEvent)
    self.Bind(wx.EVT_LEFT_UP, self.OnMouseEvent)
    
  def OnMouseEvent(self, event):
    if event.ButtonDown(0):
      self.mouseStart=(np.array(event.GetPosition()),self.imgCoord.copy())
      print 'drag Start'
    elif event.ButtonUp(0):
      print 'drag End'
      del self.mouseStart
    else:
      try:
        (pStart,icStart)=self.mouseStart
      except AttributeError as e:
        pSz = np.array(self.GetClientSize(),np.float32)
        pMouse  = np.array(event.GetPosition(),np.float32)
        ic=self.imgCoord
        pOfs=(ic[0::4]+[.5,.5])*pSz
        tPos=(pMouse-pOfs)/(pSz-2*pOfs)#position on the image 0..1
        #print tPos 
        if (tPos<0).any() or (tPos>1).any():
          return
        data=self.data
        tPos=tPos*(ic[3::4]-ic[1::4])+ic[1::4]
        tPos[0]*=data.shape[1]
        tPos[1]*=data.shape[0]
        v=tuple(tPos.astype(np.int32))
        v=tuple(reversed(v))
        v+=(data[v],)
        self.SetStatusCB(self.Parent,0,v)

        #vS=event.GetPosition()[0]
        pass
      else: 
        #prefix:
        #p Pixel, t Texture, v vertex
        pSz = np.array(self.GetClientSize(),np.float32)
        pMouse  = np.array(event.GetPosition(),np.float32)
        ic=self.imgCoord

        pOfs=(ic[0::4]+[.5,.5])*pSz
        tOfs=(pMouse-pStart)/(pSz-2*pOfs)#position on the image 0..1
        tOfs=tOfs*(icStart[3::4]-icStart[1::4])
        
        if icStart[1]-tOfs[0]<0:
          tOfs[0]=icStart[1]
        if icStart[5]-tOfs[1]<0:
          tOfs[1]=icStart[5]
        if icStart[3]-tOfs[0]>1:
          tOfs[0]=icStart[3]-1
        if icStart[7]-tOfs[1]>1:
          tOfs[1]=icStart[7]-1
          
        #print icStart[1::4],icStart[3::4],tOfs

        ic[1::4]=icStart[1::4]-tOfs
        ic[3::4]=icStart[3::4]-tOfs
            
        self.SetZoom()
        self.Refresh(False)
    #event.Skip()
    pass

  def OnMouseWeel(self, event):
    #prefix:
    #p Pixel, t Texture, v vertex
    pSz = np.array(self.GetClientSize(),np.float32)
    pMouse  = np.array(event.GetPosition(),np.float32)
    ic=self.imgCoord    
    n=event.GetWheelRotation()
    pOfs=(ic[0::4]+[.5,.5])*pSz
    tPos=(pMouse-pOfs)/(pSz-2*pOfs)#position on the image 0..1
    if n>0:
      z=0.3
    else:
      z=-0.3
    tMin=tPos*z
    tMax=tMin+(1.0-z)
    tMin=tMin*(ic[3::4]-ic[1::4])+ic[1::4]
    tMax=tMax*(ic[3::4]-ic[1::4])+ic[1::4]
    tMin[tMin<0]=0
    tMax[tMax>1]=1
    ic[1::4]=tMin
    ic[3::4]=tMax
    #print tPos,pSz,pMouse,n,ic
    self.SetZoom()
    self.Refresh(False)

    pass

  def OnEraseBackground(self, event):
    """Process the erase background event."""
    print 'OnEraseBackground'
    pass # Do nothing, to avoid flashing on MSWin

  def OnSize(self, event):
    """Process the resize event."""
    print 'OnSize'
    if self.GetContext():
            # Make sure the frame is shown before calling SetCurrent.
      self.Show()
      self.SetCurrent()

      size = self.GetClientSize()
      self.Reshape(size.width, size.height)
      self.Refresh(False)

    event.Skip()

  def OnPaint(self, event):
    """Process the drawing event."""
    #print 'OnPaint'
    self.SetCurrent()

    # This is a 'perfect' time to initialize OpenGL ... only if we need to
    if not self.GLinitialized:
      self.InitGL()
      self.GLinitialized = True
      size = self.GetClientSize()
      self.Reshape(size.width, size.height)
      self.Refresh(False)

    glClear(GL_COLOR_BUFFER_BIT)
    ic=self.imgCoord
    self.glumpyImg.draw(ic[0],ic[4],0,ic[2]-ic[0],ic[6]-ic[4])
    self.glColBar.draw(-.5,-.5,0,1.,.02)       
    # Drawing an example triangle in the middle of the screen
    #glBegin(GL_TRIANGLES)
    #glColor(1, 0, 0)
    #glVertex(-.25, -.25)
    #glVertex(.25, -.25)
    #glVertex(0, .25)
    #glEnd()
    self.SwapBuffers()
    if event!=None:
      event.Skip()

  def SetZoom(self):
    ic=self.imgCoord
    xmin,xmax,ymin,ymax=ic[1::2];
    vert=self.glumpyImg._vertices
    n = vert.shape[0]
    u,v = np.mgrid[0:n,0:n]
    u=u*(xmax-xmin)/float(n-1)+xmin
    v=v*(ymax-ymin)/float(n-1)+ymin
    #u/=2;u+=.3
    vert['tex_coord']['u'] = u
    vert['tex_coord']['v'] = v

  def GetTxrData(self,colRng=None):
    data=self.data
    #frm=data[...].astype(np.float32)     
    txrData=5.*np.log(data[...].astype(np.float32)+1.)
    return txrData
  
  def InitGL(self):
    """Initialize OpenGL for use in the window."""
    print 'InitGL'
    glClearColor(1, 1, 1, 1)
    colMap=glumpy.colormap.Hot
    txrColBar=np.linspace(0.,1., 256).astype(np.float32)
    self.glColBar=glumpy.image.Image(txrColBar, colormap=colMap,vmin=0, vmax=1)
    
    colRng=(0,10)
    txrData=self.GetTxrData(colRng)
    self.glumpyImg=img=glumpy.image.Image(txrData, colormap=colMap,vmin=colRng[0], vmax=colRng[1])
    img.update()
    self.imgCoord=np.array([-.49,0,.49,1,-.49,0,.49,1])#xmin,xmax,umin,umax,ymin,ymax,vmin,vmax    
    pass

  def Reshape(self, width, height):
    """Reshape the OpenGL viewport based on the dimensions of the window."""
    print 'Reshape'
    glViewport(0, 0, width, height)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(-0.5, 0.5, -0.5, 0.5, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

class DlgColBarSetup(wx.Dialog):
  def __init__(self,parent):
    wx.Dialog.__init__(self,parent,-1,'Colormap Setup')
    img=parent.canvas.glumpyImg
    txtVMin=wx.StaticText(self,-1,'vmin')
    txtVMax=wx.StaticText(self,-1,'vmax')
    txtColMap=wx.StaticText(self,-1,'colormap')
    self.edVMin=edVMin=wx.TextCtrl(self,-1,'%g'%img._vmin)
    self.edVMax=edVMax=wx.TextCtrl(self,-1,'%g'%img._vmax)
    colMapLst=[]
    #adding all existing colormaps
    #MplAddAllColormaps()
    #for (k,v) in glumpy.colormap.__dict__.iteritems():
    #  if isinstance(v,glumpy.colormap.Colormap):
    #    colMapLst.append(k)
        
    #adding best existing colormaps of glumpy and mpl
    for k in ('Hot','spectral','jet','Grey','RdYlBu','hsv','gist_stern','gist_rainbow','IceAndFire','gist_ncar'):
      try:
        v=glumpy.colormap.__dict__[k]
      except KeyError as e:
        try:
          import matplotlib.cm as cm
          lut= cm.datad[k]
          MplAddColormap(k,lut)
          v=glumpy.colormap.__dict__[k]
        except ImportError as e:
          print e.message
          print "don't have colormap "+k
          continue
      if isinstance(v,glumpy.colormap.Colormap):
        colMapLst.append(k)

    self.cbColMap=cbColMap=wx.ComboBox(self, -1, choices=colMapLst, style=wx.CB_READONLY)
    
    sizer=wx.BoxSizer(wx.VERTICAL)
    fgs=wx.FlexGridSizer(3,2,5,5)
    fgs.Add(txtVMin,0,wx.ALIGN_RIGHT)
    fgs.Add(edVMin,0,wx.EXPAND)
    fgs.Add(txtVMax,0,wx.ALIGN_RIGHT)
    fgs.Add(edVMax,0,wx.EXPAND)
    fgs.Add(txtColMap,0,wx.ALIGN_RIGHT)
    fgs.Add(cbColMap,0,wx.EXPAND)
    sizer.Add(fgs,0,wx.EXPAND|wx.ALL,5)

    edVMin.SetFocus()

    btns =  self.CreateButtonSizer(wx.OK|wx.CANCEL)
    btnApply=wx.Button(self, -1, 'Apply')
    btns.Add(btnApply, 0, wx.ALL, 5)
    sizer.Add(btns,0,wx.EXPAND|wx.ALL,5)
    self.Bind(wx.EVT_BUTTON, self.OnBtnOk, id=wx.ID_OK)
    self.Bind(wx.EVT_BUTTON, self.OnBtnOk, btnApply)
    self.Bind(wx.EVT_COMBOBOX, self.OnBtnOk, cbColMap)

    self.SetSizer(sizer)
    sizer.Fit(self)

  def OnBtnOk(self, event):
    event.Skip()#do not consume (use event to close the window and sent return code)
    print 'OnBtnOk'
    parent=self.GetParent()
    canvas=parent.canvas
    img=canvas.glumpyImg
    img._vmin=float(self.edVMin.Value)
    img._vmax=float(self.edVMax.Value)
    v=self.cbColMap.Value
    if v:
      cmap=getattr(glumpy.colormap,v)
      img._filter.colormap=cmap
      img._filter.build()
      cbar=canvas.glColBar
      cbar._filter.colormap=cmap
      cbar._filter.build()
      cbar.update()

    img.update()
    canvas.Refresh(False)
    
class HdfImageGLFrame(wx.Frame):
  def __init__(self, parent, title, hid):
        # Forcing a specific style on the window.
        #   Should this include styles passed?
    style = wx.DEFAULT_FRAME_STYLE | wx.NO_FULL_REPAINT_ON_RESIZE
    wx.Frame.__init__(self, parent, title=title, size=wx.Size(850, 650), style=style)
    imgDir=ut.Path.GetImage()
    icon = wx.Icon(os.path.join(imgDir,'h5pyViewer.ico'), wx.BITMAP_TYPE_ICO)
    self.SetIcon(icon)
    canvas=GLCanvasImg(self,self.SetStatusCB)

    #self.Bind(wx.EVT_IDLE, self.OnIdle)
    t = type(hid)
    if t == h5py.h5d.DatasetID:
      ds = h5py.Dataset(hid)
      self.dataSet=ds

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
    self.SetSizer(sizer)

    wxAxCtrlLst=[]
    l=len(ds.shape)
    idxXY=(l-2,l-1)
    for idx,l in enumerate(ds.shape):
      if idx in idxXY:
        continue 
      wxAxCtrl=ut.SliderGroup(self, label='Axis:%d'%idx,range=(0,l-1))
      wxAxCtrl.idx=idx
      wxAxCtrlLst.append(wxAxCtrl)
      sizer.Add(wxAxCtrl.sizer, 0, wx.EXPAND | wx.ALIGN_CENTER | wx.ALL, border=5)
      wxAxCtrl.SetCallback(HdfImageGLFrame.OnSetView,wxAxCtrl)

    sl=ut.GetSlice(idxXY,ds.shape,wxAxCtrlLst)
    

    canvas.data=ds[sl]
      
    #self.Fit()   
    self.Centre()
    
    self.BuildMenu()
    self.canvas=canvas
    self.sizer=sizer
    self.idxXY=idxXY
    self.wxAxCtrlLst=wxAxCtrlLst

  def BuildMenu(self):
    mnBar = wx.MenuBar()

    #-------- Edit Menu --------
    mn = wx.Menu()
    mnItem=mn.Append(wx.ID_ANY, 'Setup Colormap', 'Setup the color mapping ');self.Bind(wx.EVT_MENU, self.OnColmapSetup, mnItem)
    #mnItem=mn.Append(wx.ID_ANY, 'Linear Mapping', 'Use a linear values to color mapping ');self.Bind(wx.EVT_MENU, self.OnMapLin, mnItem)
    #mnItem=mn.Append(wx.ID_ANY, 'Log Mapping', 'Use a logarithmic values to color mapping ');self.Bind(wx.EVT_MENU, self.OnMapLog, mnItem)
    #mnItem=mn.Append(wx.ID_ANY, 'Invert X-Axis', kind=wx.ITEM_CHECK);self.Bind(wx.EVT_MENU, self.OnInvertAxis, mnItem)
    #self.mnIDxAxis=mnItem.GetId()
    #mnItem=mn.Append(wx.ID_ANY, 'Invert Y-Axis', kind=wx.ITEM_CHECK);self.Bind(wx.EVT_MENU, self.OnInvertAxis, mnItem)
    mnBar.Append(mn, '&Edit')
    mn = wx.Menu()
    mnItem=mn.Append(wx.ID_ANY, 'Help', 'How to use the image viewer');self.Bind(wx.EVT_MENU, self.OnHelp, mnItem)
    mnBar.Append(mn, '&Help')

    self.SetMenuBar(mnBar)
    self.CreateStatusBar()      

  @staticmethod
  def SetStatusCB(obj,mode,v):
    if mode==0:
      obj.SetStatusText( "Pos:(%d,%d) Value:%d"%v,0)

  def OnHelp(self,event):
    msg='''to change the image selection:
drag with left mouse button to move the image
use mouse wheel to zoom in/out the image at a given point
'''
    dlg = wx.MessageDialog(self, msg, 'Help', wx.OK|wx.ICON_INFORMATION)
    dlg.ShowModal()
    dlg.Destroy()

  def OnColmapSetup(self,event):
    dlg=DlgColBarSetup(self)
    if dlg.ShowModal()==wx.ID_OK:
      pass
    dlg.Destroy()

  @staticmethod
  def OnSetView(usrData,value,msg):
    'called when a slice is selected with the slider controls'
    frm=usrData.slider.Parent
    ds=frm.dataSet
    canvas=frm.canvas
    img=canvas.glumpyImg
    sl=ut.GetSlice(frm.idxXY,ds.shape,frm.wxAxCtrlLst)
    canvas.data[:]=ds[sl][:]
    img.data[:]=canvas.GetTxrData()
    img.update()
    canvas.OnPaint(None)#force to repaint, Refresh and Update do not force !
    #canvas.Refresh(False)
    #canvas.Update()
    pass


  def OnIdle(self, event):
    try:
      glumpyImg=self.canvas.glumpyImg
      ds=self.dataSet
    except AttributeError as e:
      return

    try:
      frmIdx=self.frmIdx
      frmIdx+=1
    except AttributeError as e:
      frmIdx=0
      return
    print 'OnIdle',frmIdx
    frm=ds[frmIdx,...].astype(np.float32)
    glumpyImg.data[:]=frm[:]
    glumpyImg.update()
    self.frmIdx=frmIdx
    self.canvas.Refresh(False)

if __name__ == '__main__':
  import os,sys,argparse #since python 2.7
  def GetParser(required=True):
    fnHDF='/scratch/detectorData/e14472_00033.hdf5'
    #lbl='mcs'
    lbl='pilatus_1'
    #lbl='spec'
    elem='/entry/dataScan00033/'+lbl
    exampleCmd='--hdfFile='+fnHDF+' --elem='+elem
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=__doc__,
                                     epilog='Example:\n'+os.path.basename(sys.argv[0])+' '+exampleCmd+'\n ')
    parser.add_argument('--hdfFile', required=required, default=fnHDF, help='the hdf5 to show')
    parser.add_argument('--elem', required=required, default=elem, help='the path to the element in the hdf5 file')
    return parser
    args = parser.parse_args()
    return args

  class App(wx.App):
    def OnInit(self):
      parser=GetParser()
      #parser=GetParser(False) # debug with exampleCmd
      args = parser.parse_args()
      try:
        self.fid=fid=h5py.h5f.open(args.hdfFile)
      except IOError as e:
        sys.stderr.write('Unable to open File: '+args.hdfFile+'\n')
        parser.print_usage(sys.stderr)
        return True
      try:
        hid = h5py.h5o.open(fid,args.elem)
      except KeyError as e:
        sys.stderr.write('Unable to open Object: '+args.elem+'\n')
        parser.print_usage(sys.stderr)
        return True
      frame = HdfImageGLFrame(None,args.elem,hid)
      frame.Show()
      self.SetTopWindow(frame)
      return True

    def OnExit(self):
      self.fid.close()

  ut.StopWatch.Start()
  app = App()
  app.MainLoop()
