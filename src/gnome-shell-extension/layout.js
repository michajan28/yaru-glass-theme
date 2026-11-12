import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import St from 'gi://St';

export function supportedDialog(dialog) {
    const clock = dialog?._clock;
    const parent = dialog?._stack?.get_parent();
    return Boolean(clock?._time && clock?._date && clock?._wallClock &&
        dialog._notificationsBox?.get_parent() === parent &&
        dialog._notificationsBox._scrollView instanceof St.ScrollView &&
        dialog._promptBox && dialog._user && dialog._backgroundGroup &&
        parent?.layout_manager?.vfunc_allocate);
}

export const DemoLayout = GObject.registerClass(
class DemoLayout extends Clutter.LayoutManager {
    _init(dialog, profile, original) {
        super._init();
        this._dialog = dialog;
        this._profile = profile;
        this._original = original;
        this._clockStyle = dialog._clock._time.get_style();
        this._clockSizeKey = null;
        this._scrollView = dialog._notificationsBox._scrollView;
        this._scrollState = {
            horizontal: this._scrollView.hscrollbar_policy,
            vertical: this._scrollView.vscrollbar_policy,
            overlay: this._scrollView.overlay_scrollbars,
            mouse: this._scrollView.enable_mouse_scrolling,
        };
        this._scrollView.set_policy(St.PolicyType.NEVER, St.PolicyType.AUTOMATIC);
        this._scrollView.overlay_scrollbars = false;
        this._scrollView.enable_mouse_scrolling = true;
        this._scrollView.add_style_class_name('yaru-lock-notifications-scroll');
        // Keep boundary scrolling from reaching GNOME's scroll-to-prompt handler.
        this._scrollEventId = this._scrollView.connect_after('scroll-event', () =>
            !this._dialog._promptBox.visible && this._scrollView.vscrollbar_visible
                ? Clutter.EVENT_STOP : Clutter.EVENT_PROPAGATE);
    }

    restore() {
        this._dialog._clock._time.set_style(this._clockStyle);
        this._dialog._clock.remove_style_class_name('yaru-lock-compact');
        this._scrollView.disconnect(this._scrollEventId);
        this._scrollView.set_policy(this._scrollState.horizontal, this._scrollState.vertical);
        this._scrollView.overlay_scrollbars = this._scrollState.overlay;
        this._scrollView.enable_mouse_scrolling = this._scrollState.mouse;
        this._scrollView.remove_style_class_name('yaru-lock-notifications-scroll');
    }

    _fitClock(width, height, scale, compact) {
        const clock = this._dialog._clock;
        const key = [width, height, scale, compact, clock._time.text, clock._date.text].join(':');
        if (key === this._clockSizeKey)
            return;
        this._clockSizeKey = key;
        const style = size => clock._time.set_style(
            `${this._clockStyle ? `${this._clockStyle};` : ''}font-size: ${size}px;`);
        let minimum = 24;
        let maximum = 128;
        while (minimum < maximum) {
            const size = Math.ceil((minimum + maximum) / 2);
            style(size);
            const naturalWidth = clock._time.get_preferred_size()[2];
            const naturalHeight = this._dialog._stack.get_preferred_size()[3];
            if (naturalWidth <= width && naturalHeight <= height)
                minimum = size;
            else
                maximum = size - 1;
        }
        style(minimum);
    }

    vfunc_get_preferred_width(container, height) {
        return this._original.vfunc_get_preferred_width(container, height);
    }

    vfunc_get_preferred_height(container, width) {
        return this._original.vfunc_get_preferred_height(container, width);
    }

    vfunc_allocate(container, box) {
        const dialog = this._dialog;
        this._profile.visible = !dialog._promptBox.visible;
        if (dialog._promptBox.visible) {
            this._original.vfunc_allocate(container, box);
            return;
        }
        const [width, height] = box.get_size();
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const compact = height / scale < 600 || width / scale < 400;
        for (const actor of [dialog._clock, this._profile]) {
            if (compact)
                actor.add_style_class_name('yaru-lock-compact');
            else
                actor.remove_style_class_name('yaru-lock-compact');
        }
        const margin = (compact ? 8 : 24) * scale;
        const allocate = (actor, y, maximumHeight) => {
            const [, , preferredWidth, preferredHeight] = actor.get_preferred_size();
            const actorWidth = actor === dialog._notificationsBox
                ? Math.min(360 * scale, Math.max(0, width - margin * 2))
                : Math.min(preferredWidth, Math.max(0, width - margin * 2));
            const actorHeight = Math.min(preferredHeight, Math.max(0, maximumHeight));
            const bounds = new Clutter.ActorBox();
            bounds.set_origin(Math.floor((width - actorWidth) / 2), Math.floor(y));
            bounds.set_size(actorWidth, actorHeight);
            actor.allocate(bounds);
            return actorHeight;
        };
        const [, , , profileHeight] = this._profile.get_preferred_size();
        const profileY = Math.max(margin, height - profileHeight - margin);
        allocate(this._profile, profileY, profileHeight);
        const clockY = compact ? margin : Math.min(64 * scale, height * 0.1);
        const [, , , notificationHeight] = dialog._notificationsBox.get_preferred_size();
        const reservedNotifications = Math.min(notificationHeight, 64 * scale);
        const clockBudget = Math.max(0, Math.min(height * 0.4,
            profileY - margin * 2 - clockY - reservedNotifications));
        this._fitClock(Math.max(0, width - margin * 2), clockBudget, scale, compact);
        const clockHeight = allocate(dialog._stack, clockY, clockBudget);
        const top = clockY + clockHeight + margin;
        const available = Math.max(0, profileY - margin - top);
        allocate(dialog._notificationsBox,
            Math.max(top, profileY - margin - Math.min(notificationHeight, available)),
            available);
    }
});
