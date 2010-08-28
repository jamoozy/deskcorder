import math
import cairo

def _draw_slide_on_surface(ctx, slide, scale = (400,300)):
  for stroke in slide.strokes:
    ctx.set_source_rgb(stroke.r(), stroke.g(), stroke.b())
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(stroke.first().x() * scale[0], stroke.first().y() * scale[1])
    for point in stroke.points[1:]:
      if point.x() == 0 and point.y() == 0:
        print '(0,0)'
      ctx.set_line_width(point.p * math.sqrt(scale[0]**2 + scale[1]**2))
      ctx.line_to(point.x() * scale[0], point.y() * scale[1])
    ctx.stroke()

def to_pdf(trace, ofname, size = (400,300), times = None):
  surface = cairo.PDFSurface("%s.pdf" % ofname, size[0], size[1])
  ctx = cairo.Context(surface)
  if times is None:
    for slide in trace.slides:
      _draw_slide_on_surface(ctx, slide, size)
      ctx.show_page()

def to_png(trace, ofname, size = (400,300), times = None):
  slideidx = 0
  if times is None:
    for slide in trace.slides:
      surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size[0], size[1])
      ctx = cairo.Context(surface)
      ctx.set_source_rgb(1.0,1.0,1.0)
      ctx.paint()
      _draw_slide_on_surface(ctx, slide, size)
      surface.write_to_png("%s-%03d.png" % (ofname,slideidx))
      slideidx += 1

if __name__ == "__main__":
  import sys, recorder
  trace,audio = recorder.load(sys.argv[1])
  to_pdf(trace, sys.argv[2])
  to_png(trace, sys.argv[2])
