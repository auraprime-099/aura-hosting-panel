// AURA HOSTING – Liquid Glassmorphism & File Manager JS
if (window.__AURA_MAIN_INIT__) {
    console.log("Aura main.js already initialized, skipping duplicate init.");
} else {
window.__AURA_MAIN_INIT__ = true;

$(document).ready(function() {
    // -------------------------------------------------------------
    // 1. Liquid Touch Animations (Ripple Effect on Buttons)
    // -------------------------------------------------------------
    $(document).on('click', '.btn, button, .btn-view, .user-info a', function(e) {
        let $this = $(this);
        let offset = $this.offset();
        let x = e.pageX - offset.left;
        let y = e.pageY - offset.top;

        let ripple = $('<span class="ripple"></span>');
        ripple.css({ top: y + 'px', left: x + 'px' });
        $this.append(ripple);

        setTimeout(function() {
            ripple.remove();
        }, 600);
    });

    // -------------------------------------------------------------
    // 2. 3D Tilt Effect on Glass Cards
    // -------------------------------------------------------------
    $(document).on('mousemove', '.glass-card, .file-card, .stat-card, .feature-card', function(e) {
        let $card = $(this);
        let cardWidth = $card.outerWidth();
        let cardHeight = $card.outerHeight();
        let offset = $card.offset();

        let mouseX = e.pageX - offset.left;
        let mouseY = e.pageY - offset.top;

        let rotateY = ((mouseX - cardWidth / 2) / cardWidth) * 8; // degrees
        let rotateX = -((mouseY - cardHeight / 2) / cardHeight) * 8;

        $card.css({
            transform: `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`
        });
    });

    $(document).on('mouseleave', '.glass-card, .file-card, .stat-card, .feature-card', function() {
        $(this).css({
            transform: 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)'
        });
    });

    // -------------------------------------------------------------
    // 3. Workspace Search & Filtering
    // -------------------------------------------------------------
    $('#file-search-input').on('keyup input', function() {
        let query = $(this).val().toLowerCase().trim();
        $('#file-container .file-card').each(function() {
            let name = $(this).data('name') ? $(this).data('name').toString() : '';
            if (name === '..' || name.includes(query)) {
                $(this).fadeIn(200);
            } else {
                $(this).fadeOut(200);
            }
        });
    });

    // -------------------------------------------------------------
    // 4. View Toggle (Grid vs List)
    // -------------------------------------------------------------
    $('#btn-view-grid').click(function() {
        $(this).addClass('active');
        $('#btn-view-list').removeClass('active');
        $('#file-container').removeClass('list-mode');
    });

    $('#btn-view-list').click(function() {
        $(this).addClass('active');
        $('#btn-view-grid').removeClass('active');
        $('#file-container').addClass('list-mode');
    });

    // -------------------------------------------------------------
    // 5. Real-Time System Stats Updates
    // -------------------------------------------------------------
    function updateStats() {
        if ($('#cpu').length === 0) return;
        $.get('/api/system', function(data) {
            if (data) {
                $('#cpu').text(data.cpu.toFixed(1));
                $('#mem').text(data.memory.toFixed(1));
                $('#running').text(data.running);
            }
        }).fail(function() { console.error('Stats fetch failed'); });
    }
    if ($('#cpu').length > 0) {
        updateStats();
        setInterval(updateStats, 4000);
    }

    // -------------------------------------------------------------
    // 6. 144 FPS Counter
    // -------------------------------------------------------------
    let frameCount = 0;
    let lastTime = performance.now();
    function updateFPS() {
        if ($('#fps-counter').length === 0) return;
        frameCount++;
        const now = performance.now();
        const delta = now - lastTime;
        if (delta >= 1000) {
            let fps = Math.min(Math.round((frameCount * 1000) / delta), 144);
            $('#fps-counter').text(fps);
            frameCount = 0;
            lastTime = now;
        }
        requestAnimationFrame(updateFPS);
    }
    if ($('#fps-counter').length > 0) {
        requestAnimationFrame(updateFPS);
    }

    // -------------------------------------------------------------
    // 7. Helper: Floating Toast Notification
    // -------------------------------------------------------------
    function showAlert(message, type) {
        // Create a floating toast that auto-removes
        const toast = $(`
            <div class="alert alert-${type}" style="
                position: fixed;
                top: 80px;
                right: 1.5rem;
                z-index: 99999;
                min-width: 260px;
                max-width: 400px;
                box-shadow: 0 8px 30px rgba(0,0,0,0.4);
                animation: slideDown 0.3s ease;
            ">${message}</div>
        `);
        $('body').append(toast);
        setTimeout(function() {
            toast.fadeOut(400, function() { toast.remove(); });
        }, 3500);
    }

    // -------------------------------------------------------------
    // 8. Dashboard Process Controls (Start/Stop/Restart/Logs/Delete)
    // -------------------------------------------------------------
    $(document).on('click', '.btn-start', function() {
        const btn = $(this);
        if (btn.prop('disabled') || btn.hasClass('is-busy')) return;
        const fileId = btn.data('id');
        btn.prop('disabled', true).addClass('is-busy').html('⏳ Starting...');
        $.post('/api/start/' + fileId)
            .done(function(response) {
                btn.html('▶ Start').prop('disabled', false).removeClass('is-busy');
                showAlert(response.message || 'Started successfully', 'success');
                setTimeout(() => location.reload(), 1200);
            })
            .fail(function(xhr) {
                btn.html('▶ Start').prop('disabled', false).removeClass('is-busy');
                showAlert(xhr.responseJSON?.error || 'Start failed', 'danger');
            });
    });

    $(document).on('click', '.btn-stop', function() {
        const btn = $(this);
        if (btn.prop('disabled') || btn.hasClass('is-busy')) return;
        const fileId = btn.data('id');
        btn.prop('disabled', true).addClass('is-busy').html('⏳ Stopping...');
        $.post('/api/stop/' + fileId)
            .done(function() {
                btn.html('⏹ Stop').prop('disabled', false).removeClass('is-busy');
                showAlert('Stopped successfully', 'success');
                setTimeout(() => location.reload(), 1200);
            })
            .fail(function() {
                btn.html('⏹ Stop').prop('disabled', false).removeClass('is-busy');
                showAlert('Stop failed', 'danger');
            });
    });

    $(document).on('click', '.btn-restart', function() {
        const btn = $(this);
        if (btn.prop('disabled') || btn.hasClass('is-busy')) return;
        const fileId = btn.data('id');
        btn.prop('disabled', true).addClass('is-busy').html('🔄 Restarting...');
        $.post('/api/restart/' + fileId)
            .done(function(response) {
                btn.html('🔄 Restart').prop('disabled', false).removeClass('is-busy');
                showAlert(response.message || 'Restarted successfully', 'success');
                setTimeout(() => location.reload(), 1200);
            })
            .fail(function(xhr) {
                btn.html('🔄 Restart').prop('disabled', false).removeClass('is-busy');
                showAlert(xhr.responseJSON?.error || 'Restart failed', 'danger');
            });
    });

    $(document).on('click', '.btn-logs', function() {
        const fileId = $(this).data('id');
        const logDiv = $('#log-' + fileId);
        if (logDiv.is(':visible')) {
            logDiv.slideUp(250);
        } else {
            logDiv.slideDown(250);
            $.get('/api/logs/' + fileId)
                .done(function(data) {
                    logDiv.find('pre').text(data.logs || 'No logs available');
                    if (data.missing_module) {
                        $('#install-module-' + fileId).show();
                        $('.btn-install-module[data-id="' + fileId + '"]').data('module', data.missing_module).text('📦 Install ' + data.missing_module + ' & Restart');
                    }
                })
                .fail(function() {
                    logDiv.find('pre').text('Failed to fetch logs');
                });
        }
    });

    $(document).on('click', '.btn-install-module', function() {
        const btn = $(this);
        const fileId = btn.data('id');
        const moduleName = btn.data('module');
        if (!moduleName) return;
        btn.prop('disabled', true).html('⏳ Installing ' + moduleName + '...');
        $.ajax({
            url: '/api/install_module/' + fileId,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ module_name: moduleName }),
            success: function(response) {
                showAlert('Module installed & bot restarted!', 'success');
                setTimeout(() => location.reload(), 1500);
            },
            error: function(xhr) {
                btn.prop('disabled', false).html('📦 Install ' + moduleName + ' & Restart');
                showAlert(xhr.responseJSON?.error || 'Module install failed', 'danger');
            }
        });
    });

    $(document).on('click', '.btn-delete[data-id]', function() {
        const fileId = $(this).data('id');
        if (confirm('⚠️ Delete this file permanently? This action cannot be undone.')) {
            $.post('/api/delete/' + fileId)
                .done(function() {
                    showAlert('File deleted successfully', 'success');
                    setTimeout(() => location.reload(), 1200);
                })
                .fail(function(xhr) {
                    showAlert(xhr.responseJSON?.error || 'Delete failed', 'danger');
                });
        }
    });

    // -------------------------------------------------------------
    // 9. Clickable Cards (File / Directory Navigation)
    // -------------------------------------------------------------
    $(document).on('click', '.clickable-card', function(e) {
        if ($(e.target).closest('a, button, input, form, select, textarea').length > 0) {
            return;
        }
        let url = $(this).data('url');
        if (url) {
            window.location.href = url;
        }
    });
});
}

