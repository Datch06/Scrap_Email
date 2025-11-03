// Tooltips trigger
const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))

$(document).ready(function () {
    $('#page_keyword_filter_excludeKeyword').tagsinput({
        tagClass: 'label label-white',
        maxTags: 5,
        page: 'existing_page',
    });

    $('#page_keyword_filter_save').on('click', function(event) {
        $('.table-proposals').hide();
        $('.sk-spinner_wrap').addClass('sk-loading');
    });

});

var filterValues = {
    'price': composeSliderRange(
        [
            {'min': 0, 'max': 95, 'step': 5},
            {'min': 100, 'max': 490, 'step': 10},
            {'min': 500, 'max': 950, 'step': 25},
            {'min': 1000, 'max': 10000, 'step': 100}
        ]),
    'traffic': composeSliderRange(
        [
            {'min': 0, 'max': 240, 'step': 10},
            {'min': 250, 'max': 975, 'step': 25},
            {'min': 1000, 'max': 4900, 'step': 100},
            {'min': 5000, 'max': 9750, 'step': 250},
            {'min': 10000, 'max': 50000, 'step': 1000},
            {'min': 50000, 'max': 100000, 'step': 5000},
        ]),
    'totalTraffic': composeSliderRange(
        [
            {'min': 0, 'max': 240, 'step': 10},
            {'min': 250, 'max': 975, 'step': 25},
            {'min': 1000, 'max': 4900, 'step': 100},
            {'min': 5000, 'max': 9750, 'step': 250},
            {'min': 10000, 'max': 50000, 'step': 1000},
            {'min': 50000, 'max': 100000, 'step': 5000},
        ]),
    'volume': composeSliderRange(
        [
            {'min': 0, 'max': 240, 'step': 10},
            {'min': 250, 'max': 975, 'step': 25},
            {'min': 1000, 'max': 4900, 'step': 100},
            {'min': 5000, 'max': 9750, 'step': 250},
            {'min': 10000, 'max': 50000, 'step': 1000},
            {'min': 50000, 'max': 100000, 'step': 5000},
        ]),
    'position': composeSliderRange(
        [
            {'min': 0, 'max': 120, 'step': 1}
        ]),
    'top100': composeSliderRange(
        [
            {'min': 0, 'max': 120, 'step': 1}
        ])
};

function composeSliderRange(steps)
{
    var values = [];
    steps.forEach(function (val) {
        for (let i = val['min']; i <= val['max']; i += val['step']) {
            values.push(i);
        }
    })

    return values;
}

// Rangeslider script
// Setting default values
$( ".rangeSlider" ).each(function(i,val){
    const defMin = $(this).data("defmin");
    const defMax = $(this).data("defmax");

    var filter = $(this).data('filter');

    $(this).slider({
        range: true,
        min: 0,
        max: filterValues[filter].length - 1,
        values: [filterValues[filter].indexOf(defMin), filterValues[filter].indexOf(defMax)]
    });
});

// Updating the min max values in textbox when slider changes
$(".rangeSlider").on("slide",function(event,ui){
    var filter = $(this).data('filter');

    $(this).parent().find(".minMaxVal .minVal").val(filterValues[filter][ui.values[0]]);
    $(this).parent().find(".minMaxVal .maxVal").val(filterValues[filter][ui.values[1]]);

    $('#page_keyword_filter_' + filter + '_min').val(filterValues[filter][ui.values[0]]);
    $('#page_keyword_filter_' + filter + '_max').val(filterValues[filter][ui.values[1]]);

    //to trigger price change event
    $('#page_keyword_filter_' + filter + '_min').trigger('change');
});

// Updating the min values when textbox changes
$(".minMaxVal .minVal").on("change",function(event){
    var filter = $(this).data('filter');
    $('#page_keyword_filter_' + filter + '_min').val($(this).val());
});

// Updating the max values when textbox changes
$(".minMaxVal .maxVal").on("change",function(event,ui){
    var filter = $(this).data('filter');
    $('#page_keyword_filter_' + filter + '_max').val($(this).val());
});

$('.multiple_edit_check').change(function() {
    if (this.checked) {
        $('.multiple-edit').show();
    } else if ($('.multiple_edit_check:checked').length === 0) {
        $('.multiple-edit').hide();
    }
});

$('#multipleEditPriceSubmit').on('click', function (){
    var price = $('#multipleEditPriceInput').val();
    var checkedPages = $('.multiple_edit_check:checked');
    var newPricePages = [];

    checkedPages.each(function (key, check) {
       var $data = $(check).parents('.outerDataContainer').find('.existingPagePriceSave');

       var page = $data.attr('data-existing-page');
       var site = $data.attr('data-site-id');

       newPricePages.push({'page': page, 'site': site});
    });

    $.ajax({
        type: 'POST',
        url: Routing.generate('user_exchange_existing_page_price_multiple'),
        data: {
            'pages': newPricePages,
            'price': price
        },
        dataType: 'json',
        success: function success(response) {
            toastr.success(response.message);

            checkedPages.each(function (key, check) {
                var $text = $(check).parents('.outerDataContainer').find('.existingPagePriceText');
                $text.text(price+' €');
            });
        },
        error: function error(XMLHttpRequest, textStatus, errorThrown, res) {
            toastr.error(response.message);
        }
    });


});