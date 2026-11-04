"""Capture current GTK frames instead of a potentially stale paintable cache."""
import time

from gi.repository import Gdk, GLib, Gtk


def snapshot_widget(widget, paintable):
    context = GLib.MainContext.default()
    clock = widget.get_frame_clock()
    if clock is None:
        raise RuntimeError("Render fixture requires a realized widget")
    painted = False

    def after_paint(_clock):
        nonlocal painted
        painted = True

    handler = clock.connect("after-paint", after_paint)
    try:
        widget.queue_draw()
        clock.request_phase(Gdk.FrameClockPhase.AFTER_PAINT)
        deadline = time.monotonic() + 5
        while not painted:
            while context.pending():
                context.iteration(False)
            if time.monotonic() > deadline:
                raise TimeoutError("GTK did not paint the requested fixture frame")
            time.sleep(.005)
    finally:
        clock.disconnect(handler)
    snapshot = Gtk.Snapshot.new()
    paintable.snapshot(snapshot, widget.get_width(), widget.get_height())
    return widget.get_renderer().render_texture(snapshot.to_node(), None)
