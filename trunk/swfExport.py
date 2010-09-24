import deskcorder as dc
import recorder
import swfOutput as swf
#import linux # XXX not liking this ... should be agnostic
import math
import sys
import subprocess

SWF_FPS = 15

def swfExportWithMP3(lecture, audio_data, fname):
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
    it.offset = first_ts + 1
    prog = 0 ; audio_sample_idx = 0

    import os, fcntl

    lameInput = os.mkfifo("lamein.fifo")
    lameOR, lameOW = os.pipe()
    lameProcess = subprocess.Popen( \
      "unbuffer /usr/bin/lame -r -s 44.1 --bitwidth 16 --signed --little-endian -m m --cbr -b 128 -t lamein.fifo -", stdout = lameOW, bufsize=20, shell=True)
    lameInputFile = open("lamein.fifo", "w")
    fcntl.fcntl(lameOR, fcntl.F_SETFL, fcntl.fcntl(lameOR, fcntl.F_GETFL) | os.O_NONBLOCK)

    while audio_sample_idx < len(audio_frames):
      sys.stdout.write("\x08"*lastMessageLength)
      message = "writing frame %d / %d" % (fnum+1, nframes) ; fnum += 1
      sys.stdout.write(message)
      lastMessageLength = len(message)
      sys.stdout.flush()

      #
      # write audio data
      new_sample_idx = int((prog + 1.0/SWF_FPS) * 44100) * 2
#      os.write(lameIW, audio_frames[audio_sample_idx:new_sample_idx])
      currentBlock = audio_frames[audio_sample_idx:new_sample_idx]
      lameInputFile.write(currentBlock + "\x00"*(new_sample_idx - len(currentBlock)))
      lameInputFile.flush()
      try:
        count = 0
        xx = "0"
        while xx != "":
          xx = os.read(lameOR, 1000)
          count += len(xx)
#          print "read %d (total %d bytes)" % (len(xx), count)
      except OSError:
        pass
      finally:
        print "read a total of %d bytes" % (count)
      audio_sample_idx = new_sample_idx

      #
      # write strokes
      shapes = []
      shape_extents = []
      styles = styles[-1:]
      for e in it.next(prog):
        if type(e) == dc.Slide:
          styles = []
          shapes = []
          for i in xrange(depth_count):
            swfOutput.append(swf.RemoveObject2(i+1))
          depth_count = 0
        elif type(e) == dc.Stroke:
          styles.append(map(lambda x: int(255*x), (e.r(), e.g(), e.b())))
          last_point = None
        elif type(e) == dc.Point:
          x, y, p = int(e.x() * dims[0]), int(e.y() * dims[1]), int(dimScale*e.p)
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
    lameProcess.terminate()
    os.unlink("lamein.fifo")
  swfOutput.close()
  print

def swfExportWithAudio(lecture, audio_data, fname):
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
    it.offset = first_ts + 1
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
      shapes = []
      shape_extents = []
      styles = styles[-1:]
      for e in it.next(prog):
        if type(e) == dc.Slide:
          styles = []
          shapes = []
          for i in xrange(depth_count):
            swfOutput.append(swf.RemoveObject2(i+1))
          depth_count = 0
        elif type(e) == dc.Stroke:
          styles.append(map(lambda x: int(255*x), (e.r(), e.g(), e.b())))
          last_point = None
        elif type(e) == dc.Point:
          x, y, p = int(e.x() * dims[0]), int(e.y() * dims[1]), int(dimScale*e.p)
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
  print

def swfExportNoAudio(lecture, fname):
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
  for fnum in xrange(0, nframes):
    sys.stdout.write("\x08"*lastMessageLength)
    message = "writing frame %d/%d" % (fnum+1, nframes)
    sys.stdout.write(message)
    lastMessageLength = len(message)
    sys.stdout.flush()
    shapes = []
    shape_extents = []
    prog = fnum / (float(SWF_FPS))
    styles = styles[-1:]
    for e in it.next(prog):
      if type(e) == dc.Slide:
        styles = []
        shapes = []
        for i in xrange(depth_count):
          swfOutput.append(swf.RemoveObject2(i+1))
        depth_count = 0
      elif type(e) == dc.Stroke:
        styles.append(map(lambda x: int(255*x), (e.r(), e.g(), e.b())))
        last_point = None
      elif type(e) == dc.Point:
        x, y, p = int(e.x() * dims[0]), int(e.y() * dims[1]), int(dimScale*e.p)
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
  print

def swfConvert(fname, outname):
  lecture, a_data = recorder.load_dcb(fname)
#  audio = linux.Audio()
#  audio.load_data(a_data)
#  return swfExportWithMP3(lecture, a_data, outname)
  return swfExportWithAudio(lecture, a_data, outname)
#  return swfExportNoAudio(lecture, outname)

if __name__ == "__main__":
  import sys
  swfConvert(sys.argv[1], sys.argv[2])

# as you can see, i got really far.
