import string
from typing import Any

from django import forms

from teamplayer import models

ALLOWABLE_DJ_NAME_CHARACTERS = {
    *string.ascii_letters,
    *string.digits,
    *string.punctuation,
    *" _-",
}


class EditStationForm(forms.Form):
    name = forms.CharField(max_length=128)
    action = forms.ChoiceField(choices=(("rename", "Rename"), ("remove", "Remove")))
    station_id = forms.IntegerField()

    def clean_name(self) -> str:
        name: str = self.cleaned_data["name"]

        name = name.strip()
        if name.lower() == "teamplayer":
            raise forms.ValidationError(f"“{name}” is an invalid name.")

        return name

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        assert cleaned_data is not None

        if "name" in cleaned_data:
            name = cleaned_data["name"]
            station_id = self.cleaned_data["station_id"]
            already_taken = "That name is already taken."

            try:
                station = models.Station.objects.get(name__iexact=name)
                if station.pk != station_id:
                    raise forms.ValidationError(already_taken)
            except models.Station.DoesNotExist:
                pass

        return cleaned_data


class CreateStationForm(forms.Form):
    name = forms.CharField(max_length=128)


class ChangeDJNameForm(forms.Form):
    dj_name = forms.CharField(max_length=25, required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.player = kwargs.pop("player")
        super().__init__(*args, **kwargs)

    def clean_dj_name(self) -> str:
        name: str = self.cleaned_data["dj_name"].strip()
        already_taken = "That name is already taken."

        if not name:
            return ""

        if not self.valid_name(name):
            raise forms.ValidationError(f"“{name}” is an invalid name.")

        try:
            player = models.Player.objects.get(dj_name__iexact=name)
            if player.pk != self.player.pk:
                raise forms.ValidationError(already_taken)
        except models.Player.DoesNotExist:
            pass

        return name

    def valid_name(self, name: str) -> bool:
        if name.lower() in ("dj ango", "dj_ango", "django"):
            return False

        if not set(name) <= ALLOWABLE_DJ_NAME_CHARACTERS:
            return False

        return True
