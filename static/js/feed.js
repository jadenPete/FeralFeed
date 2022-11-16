function enableTogglableIcons() {
	for (const icon of document.getElementsByClassName("icon-togglable")) {
		icon.addEventListener("mouseover", () => {
			icon.classList.remove("far")
			icon.classList.add("fa")
		})

		icon.addEventListener("mouseout", () => {
			icon.classList.remove("fa")
			icon.classList.add("far")
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
