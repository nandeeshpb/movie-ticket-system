/**
 * Movie Ticket Booking System - JavaScript
 * Handles all client-side functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initNavbar();
    initFlashMessages();
    initMovieCards();
    initSeatSelection();
    initFormValidation();
    initSearch();
    initBackToTop();
});

// ==================== NAVBAR ====================
function initNavbar() {
    const navbar = document.querySelector('.navbar');
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const navLinks = document.querySelector('.nav-links');

    // Scroll effect
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // Mobile menu toggle
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            mobileMenuBtn.innerHTML = navLinks.classList.contains('active') 
                ? '<i class="fas fa-times"></i>' 
                : '<i class="fas fa-bars"></i>';
        });
    }

    // Close mobile menu when clicking outside
    document.addEventListener('click', (e) => {
        if (navLinks && !navLinks.contains(e.target) && !mobileMenuBtn.contains(e.target)) {
            navLinks.classList.remove('active');
            if (mobileMenuBtn) {
                mobileMenuBtn.innerHTML = '<i class="fas fa-bars"></i>';
            }
        }
    });
}

// ==================== FLASH MESSAGES ====================
function initFlashMessages() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alert.style.animation = 'slideIn 0.3s ease-out reverse';
            setTimeout(() => alert.remove(), 300);
        }, 5000);

        // Close button
        const closeBtn = alert.querySelector('.alert-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                alert.style.animation = 'slideIn 0.3s ease-out reverse';
                setTimeout(() => alert.remove(), 300);
            });
        }
    });
}

// ==================== MOVIE CARDS ====================
function initMovieCards() {
    const movieCards = document.querySelectorAll('.movie-card');
    
    movieCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-10px)';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
        });
    });

    // Quick view modal
    const quickViewBtns = document.querySelectorAll('.quick-view-btn');
    quickViewBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const movieId = btn.dataset.movieId;
            openQuickView(movieId);
        });
    });
}

// ==================== SEAT SELECTION ====================
function initSeatSelection() {
    const seatLayout = document.querySelector('.seat-layout');
    if (!seatLayout) return;

    const seats = document.querySelectorAll('.seat');
    const selectedSeatsInput = document.getElementById('selected-seats');
    const selectedSeatsDisplay = document.querySelector('.selected-seats-list');
    const totalPriceDisplay = document.querySelector('.total-price');
    const ticketPrice = parseFloat(document.querySelector('.ticket-price-value')?.textContent || 0);

    let selectedSeats = [];

    seats.forEach(seat => {
        seat.addEventListener('click', () => {
            if (seat.classList.contains('booked')) return;

            const seatId = seat.dataset.seat;

            if (seat.classList.contains('selected')) {
                // Deselect seat
                seat.classList.remove('selected');
                selectedSeats = selectedSeats.filter(s => s !== seatId);
            } else {
                // Select seat
                seat.classList.add('selected');
                selectedSeats.push(seatId);
            }

            // Update hidden input
            if (selectedSeatsInput) {
                selectedSeatsInput.value = JSON.stringify(selectedSeats);
            }

            // Update display
            updateSelectedSeatsDisplay();
            updateTotalPrice();
        });
    });

    function updateSelectedSeatsDisplay() {
        if (!selectedSeatsDisplay) return;
        
        selectedSeatsDisplay.innerHTML = selectedSeats
            .map(seat => `<span class="selected-seat">${seat}</span>`)
            .join('');
    }

    function updateTotalPrice() {
        if (!totalPriceDisplay) return;
        
        const total = selectedSeats.length * ticketPrice;
        totalPriceDisplay.textContent = `Rs. ${total.toLocaleString()}`;
    }
}

// ==================== FORM VALIDATION ====================
function initFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });

        // Real-time validation
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                validateField(input);
            });

            input.addEventListener('input', () => {
                if (input.classList.contains('is-invalid')) {
                    validateField(input);
                }
            });
        });
    });

    function validateField(input) {
        const formGroup = input.closest('.form-group');
        const errorMessage = formGroup?.querySelector('.error-message');
        
        if (input.checkValidity()) {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
            if (errorMessage) errorMessage.style.display = 'none';
        } else {
            input.classList.remove('is-valid');
            input.classList.add('is-invalid');
            if (errorMessage) {
                errorMessage.textContent = input.validationMessage;
                errorMessage.style.display = 'block';
            }
        }
    }

    // Password strength indicator
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        if (input.id === 'password' || input.name === 'password') {
            input.addEventListener('input', () => {
                const strength = calculatePasswordStrength(input.value);
                updatePasswordStrength(strength);
            });
        }
    });
}

function calculatePasswordStrength(password) {
    let strength = 0;
    if (password.length >= 6) strength += 25;
    if (password.length >= 10) strength += 25;
    if (/[A-Z]/.test(password)) strength += 25;
    if (/[0-9]/.test(password)) strength += 12.5;
    if (/[^A-Za-z0-9]/.test(password)) strength += 12.5;
    return strength;
}

function updatePasswordStrength(strength) {
    const indicator = document.querySelector('.password-strength');
    if (!indicator) return;

    const bar = indicator.querySelector('.strength-bar');
    const text = indicator.querySelector('.strength-text');

    bar.style.width = `${strength}%`;

    if (strength < 25) {
        bar.style.background = '#e50914';
        text.textContent = 'Weak';
    } else if (strength < 50) {
        bar.style.background = '#f5c518';
        text.textContent = 'Fair';
    } else if (strength < 75) {
        bar.style.background = '#00a8e8';
        text.textContent = 'Good';
    } else {
        bar.style.background = '#46d369';
        text.textContent = 'Strong';
    }
}

// ==================== SEARCH ====================
function initSearch() {
    const searchInput = document.querySelector('.search-input');
    const searchForm = document.querySelector('.search-form');

    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const query = searchInput.value.trim();
            if (query) {
                window.location.href = `/movies?search=${encodeURIComponent(query)}`;
            }
        });
    }

    // Live search suggestions
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                // Can add AJAX search suggestions here
            }, 300);
        });
    }
}

// ==================== BACK TO TOP ====================
function initBackToTop() {
    const backToTopBtn = document.createElement('button');
    backToTopBtn.className = 'back-to-top';
    backToTopBtn.innerHTML = '<i class="fas fa-arrow-up"></i>';
    backToTopBtn.style.cssText = `
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: var(--primary-color);
        color: white;
        border: none;
        cursor: pointer;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease;
        z-index: 1000;
        box-shadow: 0 5px 20px rgba(229, 9, 20, 0.4);
    `;

    document.body.appendChild(backToTopBtn);

    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            backToTopBtn.style.opacity = '1';
            backToTopBtn.style.visibility = 'visible';
        } else {
            backToTopBtn.style.opacity = '0';
            backToTopBtn.style.visibility = 'hidden';
        }
    });

    backToTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// ==================== BOOKING DATE/TIME ====================
function initBookingDateTime() {
    const dateSelect = document.getElementById('show-date');
    const timeSelect = document.getElementById('show-time');
    const movieId = document.querySelector('.movie-id')?.value;

    if (dateSelect && timeSelect && movieId) {
        dateSelect.addEventListener('change', () => {
            loadAvailableSeats();
        });

        timeSelect.addEventListener('change', () => {
            loadAvailableSeats();
        });
    }
}

function loadAvailableSeats() {
    const dateSelect = document.getElementById('show-date');
    const timeSelect = document.getElementById('show-time');
    const movieId = document.querySelector('.movie-id')?.value;
    const seats = document.querySelectorAll('.seat');

    if (!dateSelect?.value || !timeSelect?.value || !movieId) return;

    fetch(`/api/get_booked_seats/${movieId}/${dateSelect.value}/${timeSelect.value}`)
        .then(response => response.json())
        .then(data => {
            seats.forEach(seat => {
                const seatId = seat.dataset.seat;
                if (data.seats.includes(seatId)) {
                    seat.classList.add('booked');
                    seat.classList.remove('selected');
                } else {
                    seat.classList.remove('booked');
                }
            });
        })
        .catch(error => console.error('Error loading seats:', error));
}

// ==================== MODAL ====================
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const activeModal = document.querySelector('.modal-overlay.active');
        if (activeModal) {
            activeModal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }
});

// ==================== ANIMATIONS ====================
function animateOnScroll() {
    const elements = document.querySelectorAll('.animate-on-scroll');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animated');
            }
        });
    }, { threshold: 0.1 });

    elements.forEach(el => observer.observe(el));
}

// ==================== BOOKING CONFIRMATION ====================
function initBookingConfirmation() {
    const confirmBtn = document.getElementById('confirm-booking');
    const bookingForm = document.getElementById('booking-form');

    if (confirmBtn && bookingForm) {
        confirmBtn.addEventListener('click', () => {
            const selectedSeats = document.querySelectorAll('.seat.selected');
            if (selectedSeats.length === 0) {
                alert('Please select at least one seat');
                return;
            }
            bookingForm.submit();
        });
    }

    // Print ticket
    const printBtn = document.getElementById('print-ticket');
    if (printBtn) {
        printBtn.addEventListener('click', () => {
            window.print();
        });
    }
}

// ==================== ADMIN DASHBOARD ====================
function initAdminDashboard() {
    // Toggle user status
    const toggleStatusBtns = document.querySelectorAll('.toggle-status-btn');
    toggleStatusBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const userId = btn.dataset.userId;
            if (confirm('Are you sure you want to change this user\'s status?')) {
                window.location.href = `/admin/toggle_user_status/${userId}`;
            }
        });
    });

    // Delete confirmation
    const deleteBtns = document.querySelectorAll('.delete-btn');
    deleteBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            if (!confirm('Are you sure you want to delete this item?')) {
                e.preventDefault();
            }
        });
    });

    // Chart initialization (if Chart.js is included)
    initCharts();
}

function initCharts() {
    // Revenue chart
    const revenueChart = document.getElementById('revenue-chart');
    if (revenueChart && typeof Chart !== 'undefined') {
        new Chart(revenueChart, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Revenue',
                    data: [12000, 19000, 15000, 25000, 22000, 30000],
                    borderColor: '#e50914',
                    backgroundColor: 'rgba(229, 9, 20, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
}

// ==================== IMAGE UPLOAD PREVIEW ====================
function initImagePreview() {
    const imageInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
    
    imageInputs.forEach(input => {
        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            const preview = document.querySelector(`#${input.id}-preview`);
            
            if (file && preview) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
    });
}

// ==================== COUNTDOWN TIMER ====================
function initCountdown() {
    const countdownElements = document.querySelectorAll('.countdown');
    
    countdownElements.forEach(element => {
        const targetDate = new Date(element.dataset.target).getTime();
        
        const timer = setInterval(() => {
            const now = new Date().getTime();
            const distance = targetDate - now;
            
            if (distance < 0) {
                clearInterval(timer);
                element.innerHTML = 'EXPIRED';
                return;
            }
            
            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);
            
            element.innerHTML = `${days}d ${hours}h ${minutes}m ${seconds}s`;
        }, 1000);
    });
}

// ==================== LOADING SPINNER ====================
function showLoading() {
    const loader = document.createElement('div');
    loader.className = 'loading-page';
    loader.id = 'global-loader';
    loader.innerHTML = `
        <div class="logo">Movie<span>Book</span></div>
        <div class="loading-spinner"></div>
    `;
    document.body.appendChild(loader);
}

function hideLoading() {
    const loader = document.getElementById('global-loader');
    if (loader) {
        loader.style.opacity = '0';
        setTimeout(() => loader.remove(), 300);
    }
}

// Show loading on form submit
document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn && !submitBtn.classList.contains('loading')) {
            submitBtn.classList.add('loading');
            submitBtn.disabled = true;
            showLoading();
        }
    });
});

// ==================== SMOOTH SCROLL ====================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        if (href !== '#') {
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    });
});

// ==================== ESCAPE HTML ====================
function escapeHtml(text) {
    const map = {
        '&': '&',
        '<': '<',
        '>': '>',
        '"': '"',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ==================== FORMAT CURRENCY ====================
function formatCurrency(amount, currency = 'Rs. ') {
    return `${currency}${parseFloat(amount).toLocaleString('en-IN')}`;
}

// ==================== FORMAT DATE ====================
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-IN', options);
}

function formatTime(timeString) {
    const [hours, minutes] = timeString.split(':');
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const hour12 = hour % 12 || 12;
    return `${hour12}:${minutes} ${ampm}`;
}

// Export functions for use in other files
window.MovieApp = {
    openModal,
    closeModal,
    showLoading,
    hideLoading,
    formatCurrency,
    formatDate,
    formatTime,
    escapeHtml
};
