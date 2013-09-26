/*global $*/
var MainView = (function () {
    'use strict';
    return {
        init: function () {
            MainView.views = $('#main_view > .view');
            MainView.views.hide();

            MainView.trays = $('#tray > .tray');
            MainView.trays.hide();
        },

        show: function (name) {
            var id = '#' + name,
                view = $(id),
                tray = $(id + '_tray');

            MainView.views.hide();
            MainView.trays.hide();
            view.show();
            view.find('.focus').focus();
            tray.show();
            tray.find('.focus').focus();

        }
    };
}());

$(function () {
    'use strict';
    MainView.init();
    MainView.show('queue');
});
