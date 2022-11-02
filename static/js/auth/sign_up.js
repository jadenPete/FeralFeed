const password = document.getElementById("password-input")
const confirmPassword = document.getElementById("confirm-password-input")

confirmPassword.addEventListener("input", () => {
	if (password.value == confirmPassword.value) {
		confirmPassword.setCustomValidity("")
	} else {
		confirmPassword.setCustomValidity("Password and password confirmation must match.")
		confirmPassword.reportValidity()
	}
})

const form = document.querySelector(".form")

form.addEventListener("submit", event => {
	event.preventDefault()

	fetch("/sign-up", {
		method: "post",
		body: new FormData(form)
	}).then(response => {
		if (response.status != 200) {
			document.querySelector(".error").style.setProperty("display", "block", "important")
		} else {
			const next = new URLSearchParams(window.location.search).get("next")

			if (next == undefined) {
				window.location.href = "/"
			} else {
				window.location.href = next
			}
		}
	})
})
