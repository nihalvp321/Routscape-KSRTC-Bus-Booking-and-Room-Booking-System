document.addEventListener("DOMContentLoaded", function () {
    let heroContent = document.querySelector(".hero-content");
    let aboutContent = document.querySelector(".about-content");

    function revealOnScroll(element) {
        let sectionTop = element.getBoundingClientRect().top;
        let windowHeight = window.innerHeight;

        if (sectionTop < windowHeight - 100) {
            element.classList.add("show");
        }
    }

    window.addEventListener("scroll", function () {
        revealOnScroll(heroContent);
        revealOnScroll(aboutContent);
    });

    revealOnScroll(heroContent);
    revealOnScroll(aboutContent);

    // Smooth Scrolling with Fade-in Effect
    document.querySelectorAll(".nav-links a").forEach(anchor => {
        anchor.addEventListener("click", function (e) {
            e.preventDefault(); // Prevent default jump

            const targetId = this.getAttribute("href").substring(1); // Remove #
            const targetSection = document.getElementById(targetId);

            if (targetSection) {
                window.scrollTo({
                    top: targetSection.offsetTop - 50, // Adjust offset
                    behavior: "smooth"
                });

                // Add fade-in effect after scrolling
                setTimeout(() => {
                    targetSection.classList.add("show");
                }, 500); // Delay to allow scrolling
            }
        });
    });
});


function toggleMenu() {
    document.querySelector(".nav-links").classList.toggle("active");
}

function toggleMenu() {
    document.querySelector(".nav-links").classList.toggle("active");
}

document.addEventListener("scroll", function() {
    var header = document.getElementById("header");

    if (window.scrollY > 50) {
        header.classList.add("scrolled");
    } else {
        header.classList.remove("scrolled");
    }
});

function scrollTestimonials(direction) {
    const container = document.getElementById("testimonialSlider");
    const scrollAmount = 320; // Width of card + margin

    container.scrollBy({
        left: direction * scrollAmount,
        behavior: 'smooth'
    });
}



