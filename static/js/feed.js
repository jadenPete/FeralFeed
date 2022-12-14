function enableTogglableIcons() {
	for (const icon of document.getElementsByClassName("icon-togglable")) {
		icon.addEventListener("mouseover", () => {
			icon.classList.remove("far")
			icon.classList.add("fa")
		})

		icon.addEventListener("mouseout", () => {
			if (icon.classList.contains('clicked'))
			{
				return;
			}
			icon.classList.remove("fa")
			icon.classList.add("far")
		})

		icon.addEventListener('click', () =>
		{
			icon.classList.toggle('clicked');
		})
	}
}

function toggleFavorites()
{
	for (const heart of document.getElementsByClassName('fa-heart'))
	{
		heart.addEventListener('click', () =>
		{
			if (heart.classList.contains('clicked'))
			{
				heart.classList.remove('far');
				heart.classList.remove('fa');
				
			}
		})
	}
}

function enableTooltips() {
	for (const element of document.querySelectorAll('[data-bs-toggle="tooltip"]')) {
		new bootstrap.Tooltip(element)
	}
}

enableTogglableIcons()
enableTooltips()
