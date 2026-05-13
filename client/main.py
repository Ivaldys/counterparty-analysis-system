from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from screens.login import LoginScreen
from screens.register import RegisterScreen
from screens.forgot import ForgotPasswordScreen, ForgotCodeScreen, ResetPasswordScreen
from screens.home import MainScreen
from screens.detail import DetailScreen
from screens.profile import ProfileScreen
from kivy.core.text import LabelBase
from screens.verify_email import VerifyEmailScreen

LabelBase.register(
    name="MaterialIcons",
    fn_regular="assets/fonts/MaterialIcons-Regular.ttf"
)


class RootApp(App):
    def build(self):
        Builder.load_file("kivy/screens/login.kv")
        Builder.load_file("kivy/screens/register.kv")
        Builder.load_file("kivy/screens/forgot.kv")
        Builder.load_file("kivy/screens/home.kv")
        Builder.load_file("kivy/screens/profile.kv")
        Builder.load_file("kivy/screens/detail.kv")
        Builder.load_file("kivy/screens/verify_email.kv")
        Builder.load_file("kivy/popups/upload_popup.kv")
        Builder.load_file("kivy/popups/inn_popup.kv")
        Builder.load_file("kivy/popups/weights_popup.kv")
        Builder.load_file("kivy/popups/review_popup.kv")
        Builder.load_file("kivy/popups/sort_popup.kv")
        Builder.load_file("kivy/popups/filter_popup.kv")
        sm = ScreenManager(transition=FadeTransition(duration=0.18))
        sm.add_widget(LoginScreen())
        sm.add_widget(RegisterScreen())
        sm.add_widget(ForgotPasswordScreen())
        sm.add_widget(ForgotCodeScreen())
        sm.add_widget(ResetPasswordScreen())
        sm.add_widget(MainScreen())
        sm.add_widget(ProfileScreen(name="profile"))
        sm.add_widget(DetailScreen(name="detail"))
        sm.add_widget(VerifyEmailScreen())
        return sm


if __name__ == "__main__":
    RootApp().run()