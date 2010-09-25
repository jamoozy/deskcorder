import math
import cairo
from datatypes import *
import recorder
import swfOutput as swf
#import linux # XXX not liking this ... should be agnostic
import sys
import subprocess

def _draw_slide_on_surface(ctx, slide, scale = (400,300), ts = None):
  ctx.set_line_cap(cairo.LINE_CAP_ROUND)
  for stroke in slide.strokes:
    ctx.set_source_rgb(stroke.r(), stroke.g(), stroke.b())
    ctx.move_to(stroke.first().x() * scale[0], stroke.first().y() * scale[1])
    diag_scale = math.sqrt(scale[0]**2 + scale[1]**2)
    for point in stroke.points[1:]:
      if ts is not None and ts < point.t:
        ctx.stroke()
        return
      ctx.set_line_width(stroke.thickness * point.p * diag_scale)
      ctx.line_to(point.x() * scale[0], point.y() * scale[1])
    ctx.stroke()

def _draw_to_png(fname, slide, size = (400,300), ts = None):
  surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size[0], size[1])
  ctx = cairo.Context(surface)
  ctx.set_source_rgb(1.0,1.0,1.0)
  ctx.paint()
  _draw_slide_on_surface(ctx, slide, size, ts)
  surface.write_to_png(fname)



##############################################################################
# ----------------------- Portable Document Format ------------------------- #
##############################################################################

def to_pdf(trace, ofname, size = (400,300), times = None):
  surface = cairo.PDFSurface("%s.pdf" % ofname, size[0], size[1])
  ctx = cairo.Context(surface)
  if times is None:
    print 'Writing 1 PDF page'
    for slide in trace.slides:
      _draw_slide_on_surface(ctx, slide, size)
      ctx.show_page()
  else:
    print 'Writing %d PDF %s' % \
        (len(times), 'pages' if len(times) > 1 else 'page')
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



##############################################################################
# ---------------------- Portable Network Graphics ------------------------- #
##############################################################################

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



##############################################################################
# ------------------------------ Shockwave Flash --------------------------- #
##############################################################################

SWF_FPS = 15

def _to_swf_raw_audio(lecture, audio_data, fname):
  it = iter(lecture)
  first_ts = lecture.get_time_of_first_event()
  last_ts = lecture.get_time_of_last_event()
  dur = last_ts - first_ts
  dims = (640*20,480*20) ; dimScale = 0.5 * (dims[0]**2 + dims[1]**2)**0.5
  styles = []
  obj_count = 0
  depth_count = 0

  # with compression I have to compute the number of frames beforehand
  # since it is part of the compressed data stream
  nframes = int(sum([math.ceil((len(audio_frames)*SWF_FPS)/(44100 * 2.)) for first_ts,audio_frames in audio_data]))
  swfOutput = swf.SWF(fps=SWF_FPS, size=dims, fname=fname, nframes=nframes, compression=6)
  lastMessageLength = 0

  fnum = 0

  swfOutput.append(swf.SoundStreamHead(sscount=(44100 / SWF_FPS)))
  for first_ts, audio_frames in audio_data:
    it.seek(first_ts + 1)
    prog = 0 ; audio_sample_idx = 0
    while audio_sample_idx < len(audio_frames):
      sys.stdout.write("\x08"*lastMessageLength)
      message = "writing frame %d / %d" % (fnum+1, nframes) ; fnum += 1
      sys.stdout.write(message)
      lastMessageLength = len(message)
      sys.stdout.flush()

      #
      # write audio data
      new_sample_idx = int((prog + 1.0/SWF_FPS) * 44100) * 2
      swfOutput.append(swf.SoundStreamBlock(audio_frames[audio_sample_idx:new_sample_idx]))
      audio_sample_idx = new_sample_idx

      #
      # write strokes
      thickness = 0.01
      shapes = []
      shape_extents = []
      oldStyles = styles[-1:] ; styles = []
      for e in it.next(prog):
        if type(e) == Slide:
          styles = []
          shapes = []
          for i in xrange(depth_count):
            swfOutput.append(swf.RemoveObject2(i+1))
          depth_count = 0
        elif type(e) == Stroke:
          styles.append(map(lambda x: int(255*x), (e.r(), e.g(), e.b())))
          thickness = e.thickness
          last_point = None
        elif type(e) == Point:
          x, y = int(e.x() * dims[0]), int(e.y() * dims[1])
          p = int(dimScale * thickness * e.p)
          if len(styles) == 0:
            styles = oldStyles
          if last_point:
            if len(shapes) == 0:
              shapes.append([last_point])
              shape_extents.append(2*last_point)
            shapes[-1].append((x - last_point[0], y - last_point[1], p))
            shape_extents[-1] = (min(shape_extents[-1][0], last_point[0] - p),   \
                                 min(shape_extents[-1][1], last_point[1] - p),   \
                                 max(shape_extents[-1][2], last_point[0] + p),   \
                                 max(shape_extents[-1][3], last_point[1] + p))
            shape_extents[-1] = (min(shape_extents[-1][0], x             - p),   \
                                 min(shape_extents[-1][1], y             - p),   \
                                 max(shape_extents[-1][2], x             + p),   \
                                 max(shape_extents[-1][3], y             + p))
          else:
            shapes.append([(x, y)])
            shape_extents.append(2*(x, y))
          last_point = (x,y)
        else:
          print 'WTF is a %s?' % str(type(e)) # Unhandled.
      for shapeidx in xrange(len(shapes)):
        nbits = int(math.ceil(math.log(max(len(shapes[shapeidx]) - 1, 0.5), 2)))+1
        if len(shapes[shapeidx]) <= 1:
          continue
        obj_count += 1
        swfOutput.append(swf.DefineShape2(obj_count,                             \
          swf.Rectangle(*shape_extents[shapeidx]),                               \
          swf.ShapeWithStyle(                                                    \
           [],                                                                   \
           [swf.LineStyle(2*pos[-1], swf.RGB(*styles[shapeidx]))                 \
                                                for pos in shapes[shapeidx][1:]],\
           0,                                                                    \
           nbits,                                                                \
           [swf.StyleChangeRecord(                                               \
                 x = shapes[shapeidx][0][0],                                     \
                 y = shapes[shapeidx][0][1])]                                    \
           + sum([[                                                              \
               swf.StyleChangeRecord(lineStyle = swf.binary(posidx, nbits)),     \
               swf.StraightEdgeRecord(*shapes[shapeidx][posidx][:-1])            \
             ]               for posidx in xrange(1,len(shapes[shapeidx]))], []) \
           + [swf.EndShapeRecord()]
        )))
        depth_count += 1
        swfOutput.append(                                                        \
            swf.PlaceObject2(                                                    \
              depth_count,                                                       \
              objectID = obj_count,                                              \
              placeFlagHasCharacter = True,                                      \
              placeFlagMove = False                                              \
            ))
      swfOutput.newFrame()
      prog += 1./SWF_FPS
  swfOutput.close()

def _to_swf_no_audio(lecture, fname):
  it = iter(lecture)
  first_ts = lecture.get_time_of_first_event()
  last_ts = lecture.get_time_of_last_event()
  dur = last_ts - first_ts
  dims = (640*20,480*20) ; dimScale = 0.5 * (dims[0]**2 + dims[1]**2)**0.5
  styles = []
  obj_count = 0
  depth_count = 0
  swfOutput = swf.SWF(fps=250, size=dims, fname=fname)
  lastMessageLength = 0
  nframes = int(math.ceil(dur * SWF_FPS))
  thickness = 0.01
  for fnum in xrange(0, nframes):
    sys.stdout.write("\x08"*lastMessageLength)
    message = "writing frame %d/%d" % (fnum+1, nframes)
    sys.stdout.write(message)
    lastMessageLength = len(message)
    sys.stdout.flush()
    shapes = []
    shape_extents = []
    prog = fnum / (float(SWF_FPS))
    oldStyles = styles[-1:] ; styles = []
    for e in it.next(prog):
      if type(e) == Slide:
        styles = []
        shapes = []
        for i in xrange(depth_count):
          swfOutput.append(swf.RemoveObject2(i+1))
        depth_count = 0
      elif type(e) == Stroke:
        styles.append(map(lambda x: int(255*x), (e.r(), e.g(), e.b())))
        thickness = e.thickness
        last_point = None
      elif type(e) == Point:
        x, y = int(e.x() * dims[0]), int(e.y() * dims[1])
        p = int(dimScale * thickness * e.p)
        if len(styles) == 0:
          styles = oldStyles
        if last_point:
          if len(shapes) == 0:
            shapes.append([last_point])
            shape_extents.append(2*last_point)
          shapes[-1].append((x - last_point[0], y - last_point[1], p))
          shape_extents[-1] = (min(shape_extents[-1][0], last_point[0] - p),   \
                               min(shape_extents[-1][1], last_point[1] - p),   \
                               max(shape_extents[-1][2], last_point[0] + p),   \
                               max(shape_extents[-1][3], last_point[1] + p))
          shape_extents[-1] = (min(shape_extents[-1][0], x             - p),   \
                               min(shape_extents[-1][1], y             - p),   \
                               max(shape_extents[-1][2], x             + p),   \
                               max(shape_extents[-1][3], y             + p))
        else:
          shapes.append([(x, y)])
          shape_extents.append(2*(x, y))
        last_point = (x,y)
      else:
        print 'WTF is a %s?' % str(type(e)) # Unhandled.
    for shapeidx in xrange(len(shapes)):
      nbits = int(math.ceil(math.log(max(len(shapes[shapeidx]) - 1, 0.5), 2)))+1
      if len(shapes[shapeidx]) <= 1:
        continue
      obj_count += 1
      swfOutput.append(swf.DefineShape2(obj_count,                             \
        swf.Rectangle(*shape_extents[shapeidx]),                               \
        swf.ShapeWithStyle(                                                    \
         [],                                                                   \
         [swf.LineStyle(2*pos[-1], swf.RGB(*styles[shapeidx]))                 \
                                              for pos in shapes[shapeidx][1:]],\
         0,                                                                    \
         nbits,                                                                \
         [swf.StyleChangeRecord(                                               \
               x = shapes[shapeidx][0][0],                                     \
               y = shapes[shapeidx][0][1])]                                    \
         + sum([[                                                              \
             swf.StyleChangeRecord(lineStyle = swf.binary(posidx, nbits)),     \
             swf.StraightEdgeRecord(*shapes[shapeidx][posidx][:-1])            \
           ]               for posidx in xrange(1,len(shapes[shapeidx]))], []) \
         + [swf.EndShapeRecord()]
      )))
      depth_count += 1
      swfOutput.append(                                                        \
          swf.PlaceObject2(                                                    \
            depth_count,                                                       \
            objectID = obj_count,                                              \
            placeFlagHasCharacter = True,                                      \
            placeFlagMove = False                                              \
          ))
    swfOutput.newFrame()
  swfOutput.close()

def to_swf(lecture, audio_data, fname):
  if len(audio_data) > 0:
    _to_swf_raw_audio(lecture, audio_data, fname)
  else:
    _to_swf_no_audio(lecture, fname)

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
