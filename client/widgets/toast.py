from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout

class Toast(FloatLayout):
    def __init__(self, text: str, duration: float = 2.0, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, 1)
        lbl = Label(
            text=text,
            size_hint=(.9, None),
            height=40,
            pos_hint={"center_x": 0.5, "y": 0.02},
        )
        self.add_widget(lbl)
        Clock.schedule_once(lambda dt: self.parent and self.parent.remove_widget(self), duration)