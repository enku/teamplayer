/* Primary work to be done when the page loads */
function () {
    'use strict';
    SongWidget.changesong();
    TeamPlayer.websocket_connect();
    $('#dj_name_link').click(TeamPlayer.show_dj_dialog);
    $('#preferences').click(TeamPlayer.toggle_controls);
    $('.control').click(function () { 
        setTimeout(TeamPlayer.toggle_controls, 150);
    });
    $('.current_station').disableSelection();
    $('.current_station').dblclick(function () {
        MainView.show('stations');
    });

    $('#fileupload').fileupload();

    $('#fileupload').bind('fileuploadadd', function (e, data) {
        var file = data.files[0],
            name = file.name,
            entry;

        $('#welcome').hide();
        entry = $('#current_uploads').append(ich.upload_file({name: name}));
        entry.find('.cancel_upload_button').click(function () {
            data.jqXHR.abort();
            $(this).remove();
        });
    });

    $('#fileupload').bind('fileuploadfail', function (e, data) {
        var file = data.files[0],
            name = file.name;

        $('.song_entry[data-name="' + name + '"]').remove();
    });

    $('#fileupload').bind('fileuploadprogress', function (e, data) {
        var percentage,
            file = data.files[0],
            name = file.name,
            entry;

        percentage = data.loaded * 100.0 / data.total;
        entry = $('.song_entry[data-name="' + name + '"] .upload_progress');
        entry.css('width', percentage + '%');
    });

    $('#fileupload').bind('fileuploaddone', function (e, data) {
        var file = data.files[0],
            name = file.name,
            result = data.result,
            s;

        $('.song_entry[data-name="' + name + '"]').fadeOut(function (){
            $(this).remove();
        });

        if (result.hasOwnProperty('fail')) {
            $.pnotify({
                title: 'Upload Failed',
                text: result.fail,
                type: 'error'
            });
            return;
        }

        $('#welcome').hide();
        s = ich.song_template(result);
        TeamPlayer.add_row(s);
    });

    $('#dj_name_form').ajaxForm(TeamPlayer.change_dj_name);

    $('.file.button').click(function () {
        $(this).find('input[type=file]')[0].click();
    });

    // CTRL-F activates the Library view.
    window.addEventListener("keydown", function (e) {
        if (e.ctrlKey && e.keyCode === 70) {
            e.preventDefault();
            MainView.show('library');
        }
    });

    $('#mute_button').click(function () {
        TeamPlayer.toggle_mute(this);
    });
}
