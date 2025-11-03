"use strict";
function editPrice(element) {
    var $wrapper = $(element).parents('.outerDataContainer');
    var $text = $wrapper.find('.existingPagePriceText');
    var $input = $wrapper.find('.existingPagePriceInput');
    var $save = $wrapper.find('.existingPagePriceSave');

    $text.hide();
    $input.show();
    $save.show();
    $(element).hide();
}

function applyFilter(page, search = null, orderBy = null, tab = 'all', visibility = false) {
    getAllRequestData(page);

    $("#quickPurchaseTable tbody tr").detach();

    var urlParams = page ? {page: page} : {};

    $('.exchange_sites_table').find('.sk-spinner_wrap').addClass('sk-loading');

    if (typeof proposalId !== 'undefined' && proposalId) {
        urlParams['proposal-id'] = proposalId;
    }

    if (orderBy) {
        urlParams['order-by'] = orderBy;

        var urlObject = new URL(location.href);
        var toDelete = urlObject.href.match('order-by%5B.*%5D');
        if (toDelete) {
            urlObject.searchParams.delete(decodeURI(toDelete[0]));
        }

        urlObject.searchParams.set('order-by['+Object.keys(orderBy)[0]+']', Object.values(orderBy)[0]);

        window.history.pushState({'order-by':orderBy}, null, urlObject.href);
    }

    if (search) {
        urlParams['search'] = search;
    }

    if (tab === 'join' && $('#sub_account').is(":checked")) {
        urlParams['sub_account'] = 1;
    }

    var form_filters = new FormData(document.forms.filters);

    form_filters.append('tab', tab);

    form_filters.append('visibility', visibility);

    $.ajax({
        method: "POST",
        data: form_filters,
        url: Routing.generate('user_exchange_site_find', urlParams),
        processData: false,
        contentType: false,
        success: function (response) {
            $('body').css('overflow', 'auto');
            $('.group-num').hide();
            // if (tab != "join") {
            //     $('.group-num-spinner').addClass('group-show');
            //     $.ajax({
            //         method: "POST",
            //         data: form_filters,
            //         url: Routing.generate('user_exchange_proposition_group_count'),
            //         processData: false,
            //         contentType: false,
            //         success: function (response) {
            //             $('.group-num').text(response.count);
            //             $('.group-num-spinner').removeClass('group-show');
            //             $('.group-num').show();
            //         },
            //     });
            // }

            $('#tab-find_sites .quickpurchase-table').parent().replaceWith(response);
            $('#count_results').text(countResults);
            if ($('.j-directories-list_nav .active a').attr("data-type") == "join") {
                $('.group-num').text(countResults);
                $('.group-num').show();
            } else {
                $('.group-num').hide();
            }

            $('.favorite-count').show();
            $('.bestPrice-count').show();

            initFreeze();
            tooltipshow();

            if(superAdmin){
                var columnDefs = [
                    { responsivePriority: 2, targets: 0 },
                    { responsivePriority: 2, targets: 1 },
                    { responsivePriority: 2, targets: 5 },
                    { responsivePriority: 2, targets: 3 },
                    { responsivePriority: 2, targets: 4 },
                    { responsivePriority: 2, targets: 9 },
                    { responsivePriority: 2, targets: 9 },
                    { responsivePriority: 2, targets: 10 },
                    { responsivePriority: 1, targets: 12 },
                    { responsivePriority: 3, targets: 2 },
                    { responsivePriority: 4, targets: 11 },
                    { responsivePriority: 5, targets: 7 },
                    { responsivePriority: 6, targets: 6 },
                    { responsivePriority: 7, targets: 8 }
                ];
                
                if($("#quickPurchaseTable thead tr").children("th").length > 13){
                    columnDefs.push(
                        { responsivePriority: 1, targets: 13 }  // For example, 13th column
                    );
                } 
            } else{
                var columnDefs = [
                    { responsivePriority: 2, targets: 0 },
                    { responsivePriority: 2, targets: 1 },
                    { responsivePriority: 2, targets: 3 },
                    { responsivePriority: 2, targets: 7 },
                    { responsivePriority: 2, targets: 8 },
                    { responsivePriority: 1, targets: 10 },
                    { responsivePriority: 3, targets: 2 },
                    { responsivePriority: 4, targets: 9 },
                    { responsivePriority: 5, targets: 5 },
                    { responsivePriority: 6, targets: 4 },
                    { responsivePriority: 7, targets: 6 }
                ];
            }

            $('.dataTable').DataTable({
                "language": {
                    "emptyTable": translations.name.emptyTable,
                },
                bPaginate: false,
                responsive: {
                    details: {
                        type: 'column',
                        target: ''
                    }
                },
                columnDefs: columnDefs,
                ordering: false,
                info:     false,
                buttons: [],
                initComplete: function(settings, json){
                    $('.lazy-exchange-site').lazy();
                }
            });

            $('.sticky-thead').addClass("dataTable");

            $('.exchange_site_order_by').click(function(event) {

                var order = 'asc';

                if(!$(this).hasClass('sorting_desc')) {
                    $('.exchange_site_order_by').removeClass('sorting_desc').removeClass('sorting_asc');
                    $(this).addClass('sorting_desc');

                    order = 'desc';
                } else {
                    $('.exchange_site_order_by').removeClass('sorting_desc').removeClass('sorting_asc');
                    $(this).addClass('sorting_asc');
                }

                page = location.href.match(new RegExp("page=(\\d+)"));
                var url = new URL(location.href);
                var params = new URLSearchParams(url.search);
                var search = params.get("search");

                var orderByName = $(this).attr('data-name');

                if ($("#active_site_account").val() > 0) {
                    var lowVisibility = true;
                } else {
                    var lowVisibility = false;
                }

                applyFilter(page ? page[1] : 1, search, {[orderByName]: order}, tab, lowVisibility);
                event.preventDefault();
            });

            $('.exchange_sites_table').find('.sk-spinner_wrap').removeClass('sk-loading');

            $('.i-checks').iCheck({
                checkboxClass: 'icheckbox_square-green',
                radioClass: 'iradio_square-green',
            });


            $(".sub-account-checkbox").on('ifChanged', '.i-checks', function() {
                applyFilter(page, search, orderBy, tab);
            });
        },
    });
}

function savePrice(element) {
    var $wrapper = $(element).parents('.outerDataContainer');
    var $text = $wrapper.find('.existingPagePriceText');
    var $input = $wrapper.find('.existingPagePriceInput');
    var $edit = $wrapper.find('.existingPagePriceEdit');
    var $save = $wrapper.find('.existingPagePriceSave');

    var page = $(element).attr('data-existing-page');
    var site = $(element).attr('data-site-id');
    var price = $input.val();

    $.ajax({
        type: 'POST',
        url: Routing.generate('user_exchange_existing_page_price', {'id': site}),
        data: {
            'page': page,
            'price': price
        },
        dataType: 'json',
        success: function success(response) {
            toastr.success(response.message);
            $text.text(price+' €');
            $text.show();
            $edit.show();
            $input.hide();
            $save.hide();
        },
        error: function error(XMLHttpRequest, textStatus, errorThrown, res) {
            toastr.error(response.message);
        }
    });
}

function excludeExistingPage(element) {
    var page = $(element).attr('data-existing-page');
    var site = $(element).attr('data-site-id');

    swal({
        title: translations.modal.confirmation.title,
        text: translations.modal.confirmation.text,
        type: "warning",
        showCancelButton: true,
        confirmButtonColor: "#ed5565",
        confirmButtonText: translations.modal.confirmation.confirmButtonText,
        closeOnConfirm: true
    }, function () {
        $.ajax({
            type: 'POST',
            url: Routing.generate('user_exchange_existing_page_blacklist', {id: site}),
            data: {
                'pages': page,
            },
            dataType: 'json',
            success: function success(response) {
                toastr.success('Done');
            },
            error: function error(XMLHttpRequest, textStatus, errorThrown, res) {
                var response = XMLHttpRequest.responseJSON;
                toastr.error(response.message ?? 'Unexpected error happened');
            }
        });
    });
}

$(document).ready(function () {

    var exchangeSiteProposition = $('#exchangeSiteProposition, #exchangeSitePropositionPack');
    var exchangeSitePropositionApi = $('#exchangeSitePropositionApi');
    var submitTextProposition = $('#submitTextProposition');
    var submitArticleProposition = $('#submitArticleProposition');
    var erefererAlerts = $('#erefererAlerts');
    var $filterArticleElement = $('#filters_article').parents('.fileinput');
    var exchangeSiteSenderMessage = $('#proposalEditLinks');

    $(document).on("mouseover", ".more-information-ereferer", function () {
        $(".writing-tooltip").css("display", "block");
    });

    exchangeSiteSenderMessage.on('show.bs.modal', function (e) {
        var that = $(this);
        that.find('.modal-title').html("");
        that.find('.modal-body').html("");
        var $invoker = $(e.relatedTarget);
        var id = $invoker.data('id');

        $.ajax({
            type: 'GET',
            url: Routing.generate('admin_proposal_edit_links', {
                proposal: id
            }),
            dataType: 'json',
            success: function success(response) {
                that.find('.modal-title').html(response.title);
                that.find('.modal-body').html(response.body);
            }
        });
    }).on('click', '#edit_links_submit', function (event) {
        event.preventDefault();
        var form = $('form[name="proposal_links"]');
        var id = form.find('#proposal_id').val();
        var formData = form.serialize();
        $('form[name="proposal_links"] *').prop("disabled", true);
        $.ajax({
            type: 'POST',
            url: Routing.generate('admin_proposal_edit_links', {
                proposal: id
            }),
            data: {
                'form': formData,
            },
            cache: false,
            dataType: 'json',
            success: function success(response) {
                var $urlLinks = $('#proposal_' + response.id + '_checkLinks');
                var linksHtml = '';
                var linksData = response.data;
                for(const link in linksData){
                    linksHtml += `<p><a href="${linksData[link].url}" target="_blank">${linksData[link].anchor}</a></p>`;
                }
                $urlLinks.html(linksHtml);
                $('#proposalEditLinks').modal('toggle');
            }
        });
    });

    $(document).on("mouseleave", ".more-information-ereferer", function () {
        $(".writing-tooltip").css("display", "none");
    });

    $(document).on("click", ".custom-select-wrapper", function(){
        $('.custom-select').toggleClass('open');
    });

    $(document).on("click", ".custom-option", function(){
        if (!$(this).hasClass('selected')) {
        
            $(this).parent().find('.custom-option.selected').removeClass('selected');
            $(this).addClass('selected');
            $(this).closest('.custom-select').find('.custom-select__trigger span').html($(this).html());
            $('#user_writing_ereferer_extraCount').val($(this).attr('data-value'));
        }
    });

    $(document).on("click", "#article_additional_price", function () {
        var id = $(this).val();
        $.ajax({
            type: 'GET',
            url: Routing.generate('additional_price'),
            data: {
                'id': id,
                'packOrderId': $("#packOrderId").val()
            },
            dataType: 'json',
            success: function success(response) {
                if (response.result == 'success') {
                    var charged_price = $('#charged_price').text();
                    var credits_price = $('#credits_price').text();

                    var real_price = parseFloat(charged_price);
                    var blog_price = parseFloat(credits_price);
                    $('#charged_price').text(real_price.toFixed(2));
                    $('#credits_price').text(blog_price.toFixed(2));

                }
            }
        });
    })


    $(document).on("change", "#user_writing_ereferer_extraWords", function(){ 
        var id = $("#eSid").val();
        var countWord =  $('.custom-option.selected').attr('data-value');
        if ($(this).is(':checked')) {
          $('.custom-select-wrapper').fadeIn(200);
          if (countWord > 0) {
            validatedExtraWord(id, countWord, "true");
          }
        } else {
          $('.custom-select-wrapper').fadeOut(200);
          $('#user_writing_ereferer_extraCount').val('');
          validatedExtraWord(id, 0, "true");
        }
    });

    $(document).on("change", "#user_writing_ereferer_samplePublish", function(){
        var id = $("#eSid").val();
        var wordCount = $(this).attr('data-value');
        validatedExtraWord(id, wordCount, "true");
    });

    $(document).on("change", ".writing-erefere-copywriting-container input", function(){ 
        var id = $("#eSid").val();
        if ($("#user_writing_ereferer_indexingStatus").is(':checked')) {
            var indexation = 1
        } else {
            var indexation = 0
        }
        if ($("#user_writing_ereferer_samplePublish").is(':checked')) {
            var discount = 0.9;
        } else {
            var discount = 1;
        }
        const checkedAddtionalOptions = $('#user_writing_ereferer_extraWords').prop('checked');
        $("#user_writing_ereferer_copywritingExpress").val($("#erefere-express-condition-1").is(':checked'));
        const selectedExtraWord = $('.extra-words .custom-option.selected');
        const Extrawordscount = checkedAddtionalOptions && selectedExtraWord.length > 0 ? selectedExtraWord.eq(0).attr('data-value') : 0;
        const countWords = $("#user_writing_ereferer_countWords").val();
       
        $.ajax({
          type: 'GET',
          url: Routing.generate('additional_price'),
          data: {
             'id': id,
             'wordCount': Extrawordscount,
             'express': $("#erefere-express-condition-1").is(':checked'),
             'packOrderId': $("#packOrderId").val()
          },
          dataType: 'json',
          success: function success(response) {
            if (response.result == 'success') {
              var real_price = parseFloat(response.totalPrice) + parseFloat(response.extraPrice) + parseFloat(response.expressPrice) + indexation;
              var article_price = parseFloat(response.redactionPrice) + parseFloat(response.extraPrice) + parseFloat(response.expressPrice) + indexation;
              var discountStatus = response.discount;
              if (discountStatus) {
                var discunt_price = 0.95;
              } else {
                var discunt_price = 1;
              }
              $('#charged_price').text((real_price*discount*discunt_price).toFixed(2));
              $('.article_price').text((article_price*discount*discunt_price).toFixed(2));
              $('.total-charged-price').text((real_price*discount*discunt_price).toFixed(2));
            } else {
              var real_price = parseFloat(response.totalPrice) + indexation;
              var article_price = parseFloat(response.redactionPrice) + indexation;
              $('#charged_price').text((real_price*discount).toFixed(2));
              $('.article_price').text((article_price*discount).toFixed(2));
              $('.total-charged-price').text((real_price*discount).toFixed(2));
            }
          }
        });
    });

    $(document).on("click", ".custom-option", function(){ 
        var id = $("#eSid").val();
        var wordCount = $(this).attr('data-value');
        validatedExtraWord(id, wordCount, "true");
    });

    $(document).on("change", "#user_writing_ereferer_indexingStatus", function(){
        var express_fast_price = $( ".express_fast_price" ).text().replace("€", "");
        var express_normal_price = $( ".express_normal_price" ).text().replace("€", "");
        var total_charged_price = $( ".total-charged-price" ).text().replace("€", "");
        var article_price = $('.article_price').text();

        if ($(this).is(':checked')) {
            $( ".express_fast_price" ).text((parseFloat(express_fast_price) + 1).toFixed(2) + "€");
            $( ".express_normal_price" ).text((parseFloat(express_normal_price) + 1).toFixed(2) + "€");
            $( ".total-charged-price" ).text((parseFloat(total_charged_price) + 1).toFixed(2) + "€");
            $( ".article_price" ).text((parseFloat(article_price) + 1).toFixed(2));
        } else {
            $( ".express_fast_price" ).text((parseFloat(express_fast_price) - 1).toFixed(2) + "€");
            $( ".express_normal_price" ).text((parseFloat(express_normal_price) - 1).toFixed(2) + "€");
            $( ".total-charged-price" ).text((parseFloat(total_charged_price) - 1).toFixed(2) + "€");
            $( ".article_price" ).text((parseFloat(article_price) - 1).toFixed(2));
        }
    });

    function validatedExtraWord(id, wordCount, status = "true") {
        if ($("#user_writing_ereferer_indexingStatus").is(':checked')) {
            var indexation = 1
        } else {
            var indexation = 0
        }

        if ($("#user_writing_ereferer_samplePublish").is(':checked')) {
            var discount = 0.9;
        } else {
            var discount = 1;
        }

        $.ajax({
          type: 'GET',
          url: Routing.generate('additional_price'),
          data: {
             'id': id,
             'wordCount': wordCount,
             'express': "true",
             'packOrderId': $("#packOrderId").val()
          },
          dataType: 'json',
          success: function success(response) {
            if (response.result == 'success') {
              var real_price = parseFloat(response.totalPrice) + parseFloat(response.extraPrice) + indexation;
              var express_price = parseFloat(response.totalPrice) + parseFloat(response.expressPrice) + parseFloat(response.extraPrice) + indexation;
              var article_price = parseFloat(response.redactionPrice) + parseFloat(response.extraPrice) + indexation;
              var normal_price = real_price;
              var discountStatus = response.discount;
              if (discountStatus) {
                var discunt_price = 0.95;
              } else {
                var discunt_price = 1;
              }
              if ($("#erefere-express-condition-1").prop('checked')) {
                real_price = real_price + parseFloat(response.expressPrice);
                article_price = article_price + parseFloat(response.expressPrice);
              }
              $('#charged_price').text((real_price*discount*discunt_price).toFixed(2));
              $('.article_price').text((article_price*discount*discunt_price).toFixed(2));
              $('.express_fast_price').text((express_price*discount*discunt_price).toFixed(2) + "€");
              $('.express_old_fast_price').text((express_price*discount).toFixed(2) + "€");
              $('.express_normal_price').text((normal_price*discount*discunt_price).toFixed(2) + "€");
              $('.express_old_normal_price').text((normal_price*discount).toFixed(2) + "€");
              $('.total-charged-price').text((real_price*discount*discunt_price).toFixed(2));
            } else {
              var real_price = parseFloat(response.totalPrice);
              var article_price = parseFloat(response.redactionPrice);
              $('#charged_price').text(real_price*discount.toFixed(2));
              $('.article_price').text(article_price*discount.toFixed(2));
              $('.total-charged-price').text(real_price*discount.toFixed(2));
            }
          }
        });
    }

    if (typeof proposalId !== 'undefined' && proposalId) {
        $('#filters_proposal')[0].value = proposalId;

        $filterArticleElement.find(".fileinput-filename").text(documentLink);
        $filterArticleElement.find('.fileinput-preview').text(documentLink);
        $filterArticleElement.addClass("fileinput-exists").removeClass("fileinput-new");
    }

    $('#filters_article').on('change', function () {
        var originalURL = window.location.href;
        var alteredURL = removeParam("proposal-id", originalURL);

        if (typeof proposalId !== 'undefined' && proposalId) {
            proposalId = null;
        }

        window.history.replaceState({}, document.title, alteredURL);
        $('#filters_proposal')[0].value = null;
    });

    function removeParam(key, sourceURL) {
        var rtn = sourceURL.split("?")[0],
            param,
            params_arr = [],
            queryString = (sourceURL.indexOf("?") !== -1) ? sourceURL.split("?")[1] : "";
        if (queryString !== "") {
            params_arr = queryString.split("&");
            for (var i = params_arr.length - 1; i >= 0; i -= 1) {
                param = params_arr[i].split("=")[0];
                if (param === key) {
                    params_arr.splice(i, 1);
                }
            }
            rtn = rtn + "?" + params_arr.join("&");
        }
        return rtn;
    }

    var ajaxError = function ajaxError(XMLHttpRequest, textStatus, errorThrown, res) {
        var response = XMLHttpRequest.responseJSON;
        exchangeSiteProposition.find('.sk-spinner_wrap').removeClass('sk-loading');
        exchangeSiteProposition.modal('hide');
        erefererAlerts.find('.modal-title').html(response.title);
        erefererAlerts.find('.modal-body').html("<span style='color: red'>" + response.body + "</span>");
        erefererAlerts.modal('show');
    };

    function validateText() {
        submitTextProposition.find('.modal-errors.alert-danger').addClass('hidden').empty();
        var error = true;
        var errorMessage = '';

        var checkOnRoyalCheckbox = function checkOnRoyalCheckbox() {
            $("#user_submit_your_article_copywritingCertify").parent().parent().find('.alert-danger').remove();
            $("#user_submit_your_article_copywritingCertify").parent().removeClass('text-danger');
            if ($("#user_submit_your_article_copywritingCertify").prop("checked") == false) {
                error = false;
                errorMessage = translations.errors['general_error'];

                $("#user_submit_your_article_copywritingCertify").parent().addClass('text-danger');
                $("#user_submit_your_article_copywritingCertify").parent().parent().prepend(
                    `<div class="alert alert-danger" role="alert">` +
                    translations.errors['checkedCondition'] +
                    `</div>`);
            }

            return true;
        };

        if (error) {
          checkOnRoyalCheckbox();
        }

        if (!error) {
            submitTextProposition.find('.modal-errors.alert-danger').removeClass('hidden').html(errorMessage);
        }

        return error;
    }

    function validate() {
        exchangeSiteProposition.find('.modal-errors.alert-danger').addClass('hidden').empty();
        var error = true;
        var errorMessage = '';
        var type = exchangeSiteProposition.find('#eStype').val();

        var checkOnEmpty = function checkOnEmpty(findClass) {
            var empty = exchangeSiteProposition.find(findClass).filter(function () {
                return this.value === "";
            });

            if (exchangeSiteProposition.find(findClass).length > empty.length) {
            } else {
                error = false;
                errorMessage = translations.errors[type].fields;
            }

            return true;
        };

        var checkOnValidUrl = function checkOnValidUrl(findClass) {
            var regURL = /^https?:\/\//i;
            var invalidUrl = exchangeSiteProposition.find(findClass).filter(function () {
                return !regURL.test(this.value);
            });

            if (exchangeSiteProposition.find('.writing_ereferer_url').length > invalidUrl.length) {
            } else {
                error = false;
                errorMessage = translations.errors['wrong_url'];
            }

            return true;
        };

        var checkOnEmptyMessage = function checkOnEmptyMessage(findId) {
            var empty = exchangeSiteProposition.find(findId).filter(function () {
                return this.value === "";
            });

            if (type === "join_group") {
                if (exchangeSiteProposition.find(findId).length > empty.length) {
                } else {
                    error = false;
                    errorMessage = translations.errors[type].message;
                }
            }

            return true;
        };

        var checkOnConditionCheckbox = function checkOnConditionCheckbox() {
            $("#user_submit_your_article_copywritingCertify").parent().parent().find('.alert-danger').remove();
            $("#user_submit_your_article_copywritingCertify").parent().removeClass('text-danger');
            if ($("#user_submit_your_article_copywritingCertify").prop("checked") == false) {
                error = false;
                errorMessage = translations.errors['general_error'];

                $("#user_submit_your_article_copywritingCertify").parent().addClass('text-danger');
                $("#user_submit_your_article_copywritingCertify").parent().parent().prepend(
                    `<div class="alert alert-danger" role="alert">` +
                    translations.errors['checkedCondition'] +
                    `</div>`);
            }

            return true;
        };

        var checkOnRefuseCheckbox = function checkOnRefuseCheckbox() {
            if ($("#erefere-refuse-condition").prop("checked") == false) {
                error = false;
                errorMessage = translations.errors['checkedRefuseCondition'];
            }

            return true;
        };

        var checkOnBlackList = function checkOnBlackList() {
            var url = $(".writing_ereferer_url").val();
            var anchor = $(".writing_ereferer_anchor").val();

            var blackLists = $(".writing_ereferer_black_list_url").val();
            var results = blackLists.split(",");

            if (url && anchor && blackLists) {
                results.forEach(function(result) {
                    let url_check = url.toLowerCase().indexOf(result.toLowerCase());
                    let anchor_check = anchor.toLowerCase().indexOf(result.toLowerCase());
                    
                    if (url_check !== -1 || anchor_check !== -1) {
                        error = false;
                        errorMessage = translations.errors['black_list_url'];
                    }
                });
            }

            return true;
        };

        switch (type) {
        case 'writing_webmaster':
        case 'writing_ereferer':
            checkOnEmpty('.writing_ereferer_url');
            checkOnRefuseCheckbox();

            if (error) {
                checkOnEmpty('.writing_ereferer_anchor');
            }

            if (error) {
                checkOnValidUrl('.writing_ereferer_url');
            }

            checkOnBlackList();

            break;

        case 'submit_your_article':
            checkOnConditionCheckbox();
            if($('.image_url').length > 0){
                checkOnEmpty('.image_url');
            }
            break;

        case 'create_group':
        case 'join_group':
            checkOnRefuseCheckbox();
            if (error) {
              checkOnEmpty('.writing_ereferer_anchor');
            }

            if (error) {
              checkOnValidUrl('.writing_ereferer_url');
            }

            if (error) {
              checkOnEmptyMessage('#user_create_group_partnerMessage');
            }

            checkOnBlackList();
            break;
        case 'admin_proposal':
            checkOnValidUrl('.writing_ereferer_url');
            if (error) {
                checkOnEmpty('.writing_ereferer_anchor');
            }
            if (!document.forms["user_admin_proposal"].reportValidity()) {
                error = false;
                errorMessage = translations.errors[type].fields;
            }

            break;

        case 'contact_partner':
            checkOnEmpty('.writing_ereferer_url');
            if (error) {
                checkOnEmpty('.writing_ereferer_anchor');
            }

            if (error) {
                checkOnValidUrl('.writing_ereferer_url');
            }

            checkOnBlackList();

            break;
        }

        if (!error) {
            exchangeSiteProposition.find('.modal-errors.alert-danger').removeClass('hidden').html(errorMessage);
            exchangeSiteProposition.animate({ scrollTop: 0 }, 'smooth');
        }

        return error;
    }

    exchangeSitePropositionApi.on('show.bs.modal', function (e) {
        var that = $(this);
        var $invoker = $(e.relatedTarget);
        var href = $invoker.data('href');
        console.log("href", href);
        var timeleft = 11;
        var downloadTimer = setInterval(function(){
            timeleft--;
            $("#countdowntimer").text(timeleft)
            if(timeleft <= 0) {
                console.log("timeleft", timeleft);
                window.location.href = href;
                clearInterval(downloadTimer);
                // window.location.href = href;
            }
        },1000);
    });

    submitArticleProposition.on('hide.bs.modal', function (e) {
        $(this).find('.modal-title').empty();
        $(this).find('.modal-body').empty();
    })

    submitTextProposition.on('show.bs.modal', function (e) {
        var that = $(this);
        //$('#submitArticleProposition').modal('hide');
        $('#submitArticleProposition').find( ".close" ).trigger( "click" );
        var $invoker = $(e.relatedTarget);
        var id = $invoker.data('id');
        var proposalId = $invoker.data('proposal');
        var packOrderId = $invoker.data('pack-order');
        submitTextProposition.find('.sk-spinner_wrap').addClass('sk-loading');
        submitTextProposition.find('.modal-errors.alert-danger').addClass('hidden');
        submitTextProposition.find('.modal-footer > .btn-primary').show();
        var url = Routing.generate('exchange_proposition.submit_your_text', {'exchangeSiteId': id, 'exchangePropositionId': proposalId, 'pack_order': packOrderId});
        $.ajax({
            type: 'GET',
            url: url,
            dataType: 'json',
            success: function success(response) {
                that.find('.modal-title').html(response.title);
                that.find('.modal-body').html(response.body);
                submitTextProposition.find('.sk-spinner_wrap').removeClass('sk-loading');
            },
            error: function error(XMLHttpRequest, textStatus, errorThrown, res) {
            }
        });
    }).on('click', '.modal-footer .btn-primary', function (event) {
        event.preventDefault();
        var id = $('#add-new-text').find('#eSid').val();
        var wordcount = tinyMCE.activeEditor.plugins.wordcount;
        $("#user_submit_your_article_text").val(tinyMCE.activeEditor.getContent());
        $("#user_submit_your_article_wordsCount").val(wordcount.getCount());
        var that = $(this);
        var form = $('#add-new-text')[0];
        if (!validateText()) {
            return;
        }
        var url = Routing.generate('exchange_proposition.submit_your_text', {'exchangeSiteId': id});
        if (form !== undefined) {
            submitTextProposition.find('.sk-spinner_wrap').addClass('sk-loading');
            sendPostRequest(
                Routing.generate('exchange_proposition.submit_your_text', {'exchangeSiteId': id}),
                new FormData(form),
                function (response) {
                    if (response.result == 'fail') {
                        var errorHtml = '<li><span class="glyphicon glyphicon-exclamation-sign"></span>';
                        for(i = 0; i < response.message.length; i ++){
                            errorHtml += response.message[i];
                            errorHtml += '<br/>'
                        }
                        errorHtml += '</li>'
                        $('#submitTextProposition').find('.modal-errors.alert-danger').removeClass('hidden').html(errorHtml);
                        if (response.imageCount > 0) {
                            $('#add-new-text').find(".url_container").html('');
                            for (var i = 1; i <= response.imageCount; i++) {
                               $('#submitTextProposition').find(".url_container").append(`<div class="form-group" style=" margin: 0 0 auto; margin-bottom: 10px">
                                    <label class="control-label">Image ${i}</label>
                                    <input required="required" type="text" id="filters_tag"
                                           name="user_submit_your_article[imageSource][${i}]"
                                           class="form-control image_url">
                                </div>`); 
                            }
                        }
                    }

                    if (response.result == 'success') {
                        tinymce.remove('#submitTextProposition textarea');
                        $('#submitTextProposition').find('.modal-title').html(response.title);
                        $('#submitTextProposition').find('.modal-body').html(response.body);
                        $('#submitTextProposition').find('.modal-footer > .btn-white').html(response.close);
                        $('#submitTextProposition').find('.modal-footer > .btn-primary').hide();
                        if (response.exchangePropositionId) {
                            $( "a[data-proposition='" + response.exchangePropositionId + "']" ).remove();
                        }
                    }

                    submitTextProposition.find('.sk-spinner_wrap').removeClass('sk-loading');

                },
                function (response) {
                    console.log(response);
                },
                {
                    processData: false,
                    contentType: false,
                    errorHandlerEnabled: false,
                }
            );
        } else {
            submitTextProposition.modal('hide');
        }
    }).on('hide.bs.modal', function (e) {
        tinymce.remove('#submitTextProposition textarea');
    });

    var exchangeSitePackAddTime = $('#exchangeSitePackAddTime');

    exchangeSitePackAddTime.on('show.bs.modal', function (e) {
        var that = $(this);
        var $invoker = $(e.relatedTarget);
        var id = $invoker.data('pack-order');

        exchangeSitePackAddTime.find('.sk-spinner_wrap').addClass('sk-loading');
        $.ajax({
            type: 'GET',
            url: Routing.generate('admin_pack_add_times'),
            data: {
                'id': id,
            },
            dataType: 'json',
            success: function success(response) {
                that.find('.modal-title').html(response.title);
                that.find('.modal-body').html(response.body);
                exchangeSitePackAddTime.find('.sk-spinner_wrap').removeClass('sk-loading');
            },
            error: ajaxError
        });
    }).on('click', '#pack_add_time_save', function (event) {
        event.preventDefault();
        var id = $('#packOrderId').val();
        var add_days = $('#pack_add_time_days').val();

        $.ajax({
            type: 'POST',
            url: Routing.generate('admin_pack_add_times'),
            data: {
                'pack-order': id,
                'add-days': add_days,
            },
            cache: false,
            dataType: 'json',
            success: function success(response) {
                exchangeSitePackAddTime.find('.modal-title').html(response.title);
                exchangeSitePackAddTime.find('.modal-body').html(response.body);
            },
            error: function error(XMLHttpRequest, textStatus, errorThrown, res) {
                var response = XMLHttpRequest.responseJSON;
                exchangeSitePackAddTime.find('.modal-body').html(response.error);
            }
        });
    })

    exchangeSiteProposition.on('show.bs.modal', function (e) {
        var that = $(this);
        var submitButton = that.find('.btn-primary').prop('disabled', true);
        var $invoker = $(e.relatedTarget);
        var id = $invoker.data('id');
        var type = $invoker.data('type');
        var packOrder = $invoker.data('packOrder');
        var existing_page = $invoker.data('existingPage');
        if (type === 'submit_your_article') {
            return;
        }
        var proposition = $invoker.data('proposition');
        var countWords = $invoker.data('countwords');
        exchangeSiteProposition.find('.modal-footer > .btn-primary').show();
        id = typeof id === 'undefined' ? null : id;
        type = typeof type === 'undefined' ? null : type;

        var data = {
            'id': id,
            'type': type,
            'proposition_id': proposition,
            'count_words': countWords,
        };

        if (existing_page) {
            data['existing_page'] = existing_page;
        }

        if (packOrder) {
            data['pack_order'] = packOrder;
        }

        $.ajax({
            type: 'GET',
            url: Routing.generate('user_exchange_site_find_modal'),
            data: data,
            dataType: 'json',
            success: function success(response) {
                if (response.result !== "fail") {
                    submitButton.prop('disabled', false);
                }

                that.find('.modal-title').html(response.title);
                that.find('.modal-body').html(response.body);
                that.find('#eSid').val(id);
                that.find('#eStype').val(type);
                if (type === "grouped_purchase") {
                  submitButton.css('display', 'none');
                }

                $('#user_submit_your_article_article').on('change', function () {
                    $('#user_submit_your_article_proposal')[0].value = null;

                });

                $("#user_submit_your_article_article").on('change', function (e) {
                    $('#user_submit_your_article_sessionId').val('');
                    $('.url_container .form-group').remove();
                });

                var article = $('#filters_article')[0] ? $('#filters_article')[0].files : [];
                if (article.length > 0) {

                    const dT = new ClipboardEvent('').clipboardData || // Firefox < 62 workaround exploiting https://bugzilla.mozilla.org/show_bug.cgi?id=1422655
                        new DataTransfer(); // specs compliant (as of March 2018 only Chrome)
                    dT.items.add(article[0]);

                    var $submitArticle = $('#user_submit_your_article_article');

                    $submitArticle[0].files = dT.files;

                    var $submitArticleElement = $submitArticle.parents('.fileinput');

                    $submitArticleElement.find(".fileinput-filename").text(article[0].name);
                    $submitArticleElement.find('.fileinput-preview').text(article[0].name);
                    $submitArticleElement.addClass("fileinput-exists").removeClass("fileinput-new");
                }

                if ($('#filters_proposal') && $('#filters_proposal')[0]) {
                    var proposal = $('#filters_proposal')[0].value;
                }

                if (proposal) {

                    $('#user_submit_your_article_proposal')[0].value = proposalId;

                    var $filterArticleElement = $('#user_submit_your_article_article').parents('.fileinput');

                    $filterArticleElement.find(".fileinput-filename").text(documentLink);
                    $filterArticleElement.find('.fileinput-preview').text(documentLink);
                    $filterArticleElement.addClass("fileinput-exists").removeClass("fileinput-new");
                }

                $("#date-of-publication-date").hide();

                $("#date-of-publication-checkbox label").change(function() {
                    let checked = $("#user_writing_ereferer_dateOfPublicationCheckbox")[0].checked;

                    if (checked) {
                        $("#date-of-publication-date").show();
                    } else {
                        $("#date-of-publication-date").hide();
                    }
                });
            },
            error: function error(XMLHttpRequest, textStatus, errorThrown, res) {
            }
        });
    }).on('hide.bs.modal', function (e) {
        $(this).find('.modal-title').empty();
        $(this).find('.modal-body').empty();
        $(this).find('.modal-errors').empty();
        $(".popover").css('display','none');
    }).on('click', '.groupe-button', function (e) {
        var that = $(this);
        var submitButton = that.find('.btn-primary').prop('disabled', true);
        var id = that.attr('data-id');
        var type = that.attr('data-type');
        exchangeSiteProposition.find('.sk-spinner_wrap').addClass('sk-loading');
        $.ajax({
          type: 'GET',
          url: Routing.generate('user_exchange_site_find_modal'),
          data: {
            'id': id,
            'type': type,
            'proposition_id': '',
            'count_words': '',
          },
          dataType: 'json',
          success: function success(response) {
            if (response.result !== "fail") {
              $('#exchangeSiteProposition').find('.btn-primary').prop('disabled', false);
            }

            that.closest('.modal-title').html(response.title);
            that.closest('.modal-body').html(response.body);
            $('#exchangeSiteProposition').find('.btn-primary').show();
            that.closest('#eSid').val(id);
            that.closest('#eStype').val(type);
            exchangeSiteProposition.find('.sk-spinner_wrap').removeClass('sk-loading');
          },
          error: function error(XMLHttpRequest, textStatus, errorThrown, res) {}
        });
    }).on('click', '.existing-group-button', function (e) {
        var that = $(this);
        var id = that.attr('data-id');
        var type = that.attr('data-type');
        var proposition_id = that.attr('data-proposition-id');
        exchangeSiteProposition.find('.sk-spinner_wrap').addClass('sk-loading');
        $.ajax({
          type: 'GET',
          url: Routing.generate('user_exchange_site_find_modal'),
          data: {
            'id': id,
            'type': type,
            'proposition_id': proposition_id,
            'count_words': '',
          },
          dataType: 'json',
          success: function success(response) {
            if (response.result !== "fail") {
              $('#exchangeSiteProposition').find('.btn-primary').prop('disabled', false);
            }

            that.closest('.modal-title').html(response.title);
            that.closest('.modal-body').html(response.body);
            $('#exchangeSiteProposition').find('.btn-primary').show();
            that.closest('#eSid').val(id);
            that.closest('#eStype').val(type);
            that.closest('#ePid').val(proposition_id);
            exchangeSiteProposition.find('.sk-spinner_wrap').removeClass('sk-loading');
          },
          error: function error(XMLHttpRequest, textStatus, errorThrown, res) {}
        });
    }).on('click', '.modal-footer .btn-primary', function (event) {
        event.preventDefault();
        if ($('#add-new-record').find('#eStype').val() == 'submit_your_article') {
            return;
        }

        if ($('#add-new-record').find('#eStype').val() == 'writing_ereferer') {
            $("#user_writing_ereferer_copywritingExpress").val($("#erefere-express-condition-1").is(':checked'));
        }
        
        if (!validate()) {
            return;
        }

        var form = $('#add-new-record');
        var file = $(form).find('input[type="file"]');

        if ((file.length !== 0 && file.get(0).files.length === 0) && !$('#user_submit_your_article_proposal')[0].value) {
            $(form).find('.form-group').addClass('has-error');
            return;
        }

        if (form !== undefined) {
            exchangeSiteProposition.find('.sk-spinner_wrap').addClass('sk-loading');
            sendPostRequest(
                Routing.generate('user_exchange_site_find_modal'),
                new FormData(form[0]),
                function (response) {
                    var responseBody = "";

                    if (response.body !== undefined) {
                        responseBody = '<p>' + response.body + '<p>';
                    } else if (response.message !== undefined) {
                        responseBody = '<p class="writing-ereferere-modal-title">' + response.message + '<p>';
                    }

                    if (response.number_places !== undefined && response.id) {
                        if (response.number_places === 0) {
                            $("#discount_place_" + response.id).closest(".main-site-info").find(".badge-bestPrice").hide();
                            $("#discount_place_" + response.id).closest(".main-site-info").find(".bage-number-limit").hide();
                        } else {
                            $("#discount_place_" + response.id).text(response.number_places);
                        }
                    }

                    if (response.valids !== undefined && response.valids.length > 0) {
                        responseBody += '<ul>';
                        $.each(response.valids, function (key, valid) {
                            responseBody += '<li>' + valid + '</li>';
                        });
                        responseBody += '</ul>';
                    }

                    if (typeof proposalId !== 'undefined' && proposalId) {
                        proposalId = null;
                    }

                    if ($('#filters_proposal')[0]) {
                        $('#filters_proposal')[0].value = '';
                    }

                    exchangeSiteProposition.find('.sk-spinner_wrap').removeClass('sk-loading');

                    exchangeSiteProposition.find('.modal-errors').html("");

                    if (response.result === 'success' || response.status === true) {
                        if (document.getElementById("filters_article")) {
                            document.getElementById("filters_article").value = "";
                        }

                        if ($filterArticleElement) {
                            $filterArticleElement.find(".fileinput-filename").text('');
                            $filterArticleElement.find('.fileinput-preview').text('');
                            $filterArticleElement.addClass("fileinput-new").removeClass("fileinput-exists");
                        }

                        exchangeSiteProposition.find('.modal-body').html(responseBody);
                        exchangeSiteProposition.find('.modal-footer > .btn-primary').hide();

                    }

                    if (typeof packOrder !== "undefined" && packOrder) {
                        location.reload();
                    }

                },
                function (response) {
                    var data = response.responseJSON;
                    if (data) {
                        if (data.message) {
                            if (!Array.isArray(data.message) && typeof data.message != 'object') {
                                data.message = [data.message]
                            }
                            var errorHtml = '';
                            for (var key in data.message) {
                                if (!(["add_image_url", "add_meta_title", "add_meta_description", "add_category"].includes(key))) {
                                    errorHtml += '<li>' + data.message[key] + '</li>';
                                } else if(exchangeSiteProposition.find('.' + key + '-error')) {
                                    exchangeSiteProposition.find('.' + key + '-error').html(data.message[key]);
                                } else {
                                    exchangeSiteProposition.find('.modal-errors').html(data.message[key])
                                }
                            }
                            exchangeSiteProposition.find('.modal-errors').html(errorHtml);
                            if (data.additionalInfo && data.additionalInfo.new_urk_fields) {

                                $('.additional_info_fields.add_url_container').show();

                                var formFields = '';
                                for (var i = 0; i < data.additionalInfo.new_urk_fields; i++) {
                                    formFields += '<div class="form-group" style=" margin: 0 0 auto; margin-bottom: 36px">' +
                                        '<label class="control-label">Image' + (i + 1) + '</label>' +
                                        '<input required type="text" id="filters_tag" name="user_submit_your_article[image_urls][' + i + ']" class="form-control image_url">' +
                                        '</div>';
                                }
                                exchangeSiteProposition.find('#user_submit_your_article_image_urls').html(formFields);
                            }

                            if (data.additionalInfo && data.additionalInfo.add_meta_title) {
                                $('.additional_info_fields.add_meta_title').show();
                                $('#user_submit_your_article_add_meta_title').prop('required', true);
                            }

                            if (data.additionalInfo && data.additionalInfo.add_meta_description) {
                                $('.additional_info_fields.add_meta_description').show();
                                $('#user_submit_your_article_add_meta_description').prop('required', true);
                            }

                            if (data.additionalInfo && data.additionalInfo.add_category) {
                                $('.additional_info_fields.add_category').show();
                                $("#user_submit_your_article_add_category option[value='']").remove();
                            }

                            $('#user_submit_your_article_additionalFields').val(JSON.stringify(data.additionalInfo));
                        }
                        exchangeSiteProposition.find('.sk-spinner_wrap').removeClass('sk-loading');
                    } else {
                        exchangeSiteProposition.find('.modal-body').html('<p>Something went wrong!</p>');
                        exchangeSiteProposition.find('.modal-footer > .btn-primary').hide();
                    }
                },
                {
                    processData: false,
                    contentType: false,
                    errorHandlerEnabled: false,
                }
            );
        } else {
            exchangeSiteProposition.modal('hide');
        }
    });

    $("#filters_ageMonth").on('input change', function (e) {
        var monthPerYear = 12;
        var monthCnt = parseInt($(this).val());
        if (monthCnt > monthPerYear) {
            $(this).val(monthPerYear);
        }
        if (monthCnt <= 0) {
            $(this).val('');
        }
    });

    $('body').on('click', '#buy_pack', function (event) {
        event.preventDefault();
        var href = $(this).attr('href');
        var tr = $(this).closest('tr');
        var exchangeSiteId = $(this).data('exchangeSite');

        var buy_pack_immediately = translations.pack.confirmation.buy_pack_immediately;
        var buy_pack_each_item = translations.pack.confirmation.buy_pack_each_item;

        if ($(this).data("whenPay") === 'immediately') {
            var confirmation_text = buy_pack_immediately.replace('&pack_price&', $(this).data('packPrice'));
        } else {
            var confirmation_text = buy_pack_each_item;
        }

        swal({
            title: '',
            text: confirmation_text,
            type: "warning",
            cancelButtonText: translations.modal.cancel.text,
            showCancelButton: true,
            confirmButtonColor: "#ed5565",
            confirmButtonText: translations.modal.confirmation.confirmButtonText,
            closeOnConfirm: true
        }, function () {
            $.post(href, {'exchange_site': exchangeSiteId}, function (data) {
                try {
                    if (data.result === 'success') {
                        $('#exchangeSitePropositionPack').modal('toggle');
                        //toastr.success(data.message, null, {timeOut: 0, extendedTimeOut: 0});
                        location.reload();
                    }
                } catch (e) {
                }
            });
        });
    });

});
