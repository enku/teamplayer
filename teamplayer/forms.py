import string

from django import forms

from teamplayer import models


class EditStationForm(forms.Form):
    name = forms.CharField(max_length=128)
    action = forms.ChoiceField(choices=(('rename', 'Rename'),
                                        ('remove', 'Remove')))
    station_id = forms.IntegerField()

    def clean_name(self):
        name = self.cleaned_data['name']
        invalid_name = '“{0}” is an invalid name.'

        name = name.strip()
        if name.lower() == 'teamplayer':
            raise forms.ValidationError(invalid_name.format(name))

        if len(name) > 128:
            raise forms.ValidationError('The name is too long.')

        return name

    def clean(self):
        cleaned_data = super(EditStationForm, self).clean()

        if 'name' in cleaned_data:
            name = cleaned_data['name']
            station_id = self.cleaned_data['station_id']
            already_taken = 'That name is already taken.'

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
    allowable_characters = (string.ascii_letters
                            + string.digits
                            + string.punctuation
                            + ' _-')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(ChangeDJNameForm, self).__init__(*args, **kwargs)

    def clean_dj_name(self):
        name = self.cleaned_data['dj_name'].strip()
        invalid_name = '“{0}” is an invalid name.'
        already_taken = 'That name is already taken.'

        if not name:
            return ''

        if not self.legal_name(name):
            raise forms.ValidationError(invalid_name.format(name))

        try:
            player = models.Player.objects.get(dj_name__iexact=name)
            if player.pk != self.user.player.pk:
                raise forms.ValidationError(already_taken)
        except models.Player.DoesNotExist:
            pass

        return name

    def legal_name(self, name):
        if name.lower() in ('dj ango', 'dj_ango', 'django'):
            return False

        for c in name:
            if c not in self.allowable_characters:
                return False

        return True
