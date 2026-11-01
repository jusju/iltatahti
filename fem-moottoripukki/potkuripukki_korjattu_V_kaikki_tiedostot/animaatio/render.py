"""Render original printable geometry, simultaneous rotations X/Y/Z, no fake mesh."""
import vtk,subprocess
from pathlib import Path
from vtk.util.numpy_support import vtk_to_numpy
ROOT=Path(__file__).resolve().parent.parent
src=ROOT/'mallit/pukki_V2_10mm_Z.stl'
out=ROOT/'animaatio/pukki_V_10mm_Z_xyz_hidas.mp4'
reader=vtk.vtkSTLReader();reader.SetFileName(str(src));reader.Update()
mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(reader.GetOutputPort())
actor=vtk.vtkActor();actor.SetMapper(mapper)
actor.GetProperty().SetColor(.74,.84,.93)
actor.GetProperty().SetMetallic(.32)
actor.GetProperty().SetRoughness(.28)
actor.SetOrigin(6.0,0,5.0)
ren=vtk.vtkRenderer();ren.SetBackground(.045,.065,.1);ren.AddActor(actor)
lighting=vtk.vtkLight();lighting.SetPosition(16,-16,23);lighting.SetIntensity(.9);ren.AddLight(lighting)
win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.AddRenderer(ren);win.SetSize(640,640)
cam=ren.GetActiveCamera();cam.SetFocalPoint(6,0,5);cam.SetPosition(31,-32,26);cam.SetViewUp(0,0,1);ren.ResetCamera();cam.Zoom(1.24)
wf=vtk.vtkWindowToImageFilter();wf.SetInput(win);wf.SetInputBufferTypeToRGB();wf.ReadFrontBufferOff()
# 12 seconds @20fps. All three rotations are simultaneous each frame.
N=240
p=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pixel_format','rgb24','-video_size','640x640','-framerate','20','-i','-','-c:v','libx264','-pix_fmt','yuv420p','-crf','22',str(out)],stdin=subprocess.PIPE)
for i in range(N):
 actor.RotateX(.64); actor.RotateY(.58); actor.RotateZ(.51)
 win.Render();wf.Modified();wf.Update()
 im=vtk_to_numpy(wf.GetOutput().GetPointData().GetScalars()).reshape((640,640,3))
 p.stdin.write(im[::-1].tobytes())
 if i==10:
  writer=vtk.vtkPNGWriter();writer.SetFileName(str(ROOT/'animaatio/esikatselu.png'));writer.SetInputConnection(wf.GetOutputPort());writer.Write()
p.stdin.close();rc=p.wait();print('video finished',rc,out,out.stat().st_size)
