(add-to-list 'load-path "@SITELISP@")
(load "ghostel-autoloads" nil t)
(setq ghostel-module-directory "@EMACSMODULES@"
      ghostel-module-auto-install nil)

;; Satisfy MELPA extensions without installing another copy of Ghostel.
(with-eval-after-load 'package
  (add-to-list 'package--builtin-versions '(ghostel @VERSION@)))
