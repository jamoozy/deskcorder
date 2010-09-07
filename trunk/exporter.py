import math
import cairo

def _draw_slide_on_surface(ctx, slide, scale = (400,300), ts = None):
  ctx.set_line_cap(cairo.LINE_CAP_ROUND)
  for stroke in slide.strokes:
    ctx.set_source_rgb(stroke.r(), stroke.g(), stroke.b())
    ctx.move_to(stroke.first().x() * scale[0], stroke.first().y() * scale[1])
    for point in stroke.points[1:]:
      if ts is not None and ts < point.t:
        ctx.stroke()
        return
      ctx.set_line_width(point.p * math.sqrt(scale[0]**2 + scale[1]**2))
      ctx.line_to(point.x() * scale[0], point.y() * scale[1])
    ctx.stroke()

def to_pdf(trace, ofname, size = (400,300), times = None):
  print 'to_pdf()'
  surface = cairo.PDFSurface("%s.pdf" % ofname, size[0], size[1])
  ctx = cairo.Context(surface)
  if times is None:
    for slide in trace.slides:
      _draw_slide_on_surface(ctx, slide, size)
      ctx.show_page()
  else:
    for ts in times:
      assigned = False
      print 'finding slide for t:%.0f' % ts
      for i in xrange(1,len(trace.slides)):
        if trace[i].t > ts:
          _draw_slide_on_surface(ctx, trace[i-1], size, ts)
          ctx.show_page()
          assigned = True
          break
      if not assigned:
        _draw_slide_on_surface(ctx, trace[i], size, ts)
        ctx.show_page()

def _draw_to_png(fname, slide, size = (400,300), ts = None):
  surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size[0], size[1])
  ctx = cairo.Context(surface)
  ctx.set_source_rgb(1.0,1.0,1.0)
  ctx.paint()
  _draw_slide_on_surface(ctx, slide, size, ts)
  surface.write_to_png(fname)

def to_png(trace, ofname, size = (400,300), times = None):
  print 'to_png()'
  slideidx = 0
  if times is None:
    for slide in trace.slides:
      _draw_to_png("%s-%03d.png" % (ofname,slideidx), slide, size)
      slideidx += 1
  else:
    for ts in times:
      assigned = False
      print 'finding slide for t:%.0f' % ts
      for i in xrange(1,len(trace.slides)):
        if trace[i].t > ts:
          _draw_to_png("%s-%03d.png" % (ofname,slideidx), trace[i-1], size, ts)
          assigned = True
          break
      if not assigned:
        _draw_to_png("%s-%03d.png" % (ofname,slideidx), trace[i], size, ts)
      slideidx += 1

def _load_from_file(fname):
  f = open(fname, 'r')
  times = []
  try:
    while True:
      line = f.next().strip()
      times.append(int(line[:-3]) * 60 + int(line[-2:]))
  except StopIteration:
    pass
  finally:
    f.close()
  return times

if __name__ == "__main__":
  import sys, recorder
  iname = sys.argv[1]
  trace,audio = recorder.load(iname)
  oname = iname[:-4] if iname[:-1].lower().endswith('.dc') else iname
  times = _load_from_file(sys.argv[2]) if len(sys.argv) == 3 else None
  if times is not None:
    tofe = min(trace.get_time_of_first_event(), audio[0][0])
    times = map(lambda x: x + tofe, times)
  to_pdf(trace, oname, (480,320), times)
  to_png(trace, oname, (480,320), times)
