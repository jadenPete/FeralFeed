const form = document.querySelector(".form")

form.addEventListener("submit", event => {
	event.preventDefault()

	fetch("/sign-in", {
		method: "post",
		body: new FormData(form)
	}).then(response => {
		if (response.status != 200) {
			document.querySelector(".error").style.setProperty("display", "block", "important")
		} else {
			window.location.href = "/"
		}
	})
})
