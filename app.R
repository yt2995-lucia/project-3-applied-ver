# =============================================================================
# app.R — DataScope A/B Usability Study
# STAT-GR5243 Project 3
#
# USAGE:
#   shiny::runApp()
#
# HOW IT WORKS:
#   Participants are randomly assigned to Group A (no guidance) or
#   Group B (with step-by-step hints). They complete 5 data tasks.
#   Task completion and timing are auto-submitted to Google Sheets.
#
# SETUP:
#   1. Deploy the Google Apps Script (see README.md)
#   2. Paste your script URL into SHEETS_URL below
#   3. Run: shiny::runApp()
#
# REQUIREMENTS:
#   install.packages(c("shiny","bslib","shinyjs","DT","ggplot2","dplyr","httr","jsonlite"))
# =============================================================================

library(shiny)
library(bslib)
library(shinyjs)
library(DT)
library(ggplot2)
library(dplyr)
library(httr)
library(jsonlite)

# ── Google Sheets submission URL ───────────────────────────────────────────────
SHEETS_URL <- "https://script.google.com/macros/s/AKfycbxLA4_4cLUQ0xUP2XFCO6LLeFii-x3kzuir4Cq7cO8o3X6iIeBaKkCGQqJ4U6KVvRSW/exec"

# ── Dataset: iris with injected missing values ─────────────────────────────────
set.seed(42)
task_data <- iris
task_data[sample(nrow(task_data), 12), "Sepal.Width"]  <- NA
task_data[sample(nrow(task_data),  7), "Petal.Length"] <- NA

# ── Task definitions ───────────────────────────────────────────────────────────
N_TASKS <- 5
TASK_LABELS <- c(
  "Explore the loaded data",
  "Understand the basic properties of each column",
  "Remove the non-numeric column from the dataset",
  "Create a histogram of the variable with the highest mean value",
  "Check the data quality of the dataset"
)

# =============================================================================
# UI
# =============================================================================
ui <- page_sidebar(
  title = tags$span(icon("magnifying-glass-chart"), " Data Explorer"),
  theme = bs_theme(version = 5, bootswatch = "flatly",
                   primary = "#2c3e50", secondary = "#18bc9c"),

  useShinyjs(),

  sidebar = sidebar(
    width = 300,

    # ── Welcome panel (before start) ──
    conditionalPanel(
      "output.show_welcome == 'yes'",
      h5("👋 Welcome", class = "fw-bold"),
      p("Complete 5 data tasks as accurately as you can.",
        "Work at your own pace — there is no time limit."),
      textInput("pid", "Participant ID", value = ""),
      actionButton("start_btn", "Start Tasks →",
                   class = "btn-primary w-100 mt-2")
    ),

    # ── Task progress panel (after start) ──
    conditionalPanel(
      "output.show_welcome == 'no'",
      h6("📋 Tasks", class = "fw-bold mb-2"),
      uiOutput("task_checklist"),
      hr(),
      uiOutput("progress_bar_ui"),
      hr(),
      # ── Post-task questions (shown when all tasks done) ──
      uiOutput("post_task_questions"),
      actionButton("submit_btn", "⬆ Submit & Finish",
                   class = "btn-success w-100")
    )
  ),

  # ── Main content ──
  tabsetPanel(
    id = "main_tabs",
    type = "tabs",

    # Welcome splash
    tabPanel(
      "Welcome",
      div(
        class = "text-center py-5",
        tags$h2("🔬 Data Analysis Task Study"),
        tags$p(class = "lead text-muted",
               "You will complete 5 short data analysis tasks."),
        tags$p("Enter your Participant ID in the sidebar, then click",
               tags$strong("Start Tasks →"), "to begin.")
      )
    ),

    # ── Task 1: View Data ──
    tabPanel(
      "1 · View Data",
      br(),
      uiOutput("hint_t1"),
      h5("Dataset Preview"),
      DTOutput("data_table"),
      hidden(div(id = "msg_t1",
                 class = "alert alert-success mt-3",
                 "✅ Task 1 complete — you viewed the dataset!"))
    ),

    # ── Task 2: Summary Stats ──
    tabPanel(
      "2 · Summary",
      br(),
      uiOutput("hint_t2"),
      h5("Summary Statistics"),
      actionButton("btn_summary", "Generate Summary",
                   class = "btn-primary mb-3"),
      verbatimTextOutput("summary_out"),
      hidden(div(id = "msg_t2",
                 class = "alert alert-success mt-3",
                 "✅ Task 2 complete — summary generated!"))
    ),

    # ── Task 3: Remove Column ──
    tabPanel(
      "3 · Remove Column",
      br(),
      uiOutput("hint_t3"),
      h5("Remove a Column"),
      div(class = "d-flex gap-2 align-items-end mb-3",
          div(selectInput("col_to_remove", "Select column:",
                          choices = NULL, width = "200px")),
          div(class = "mb-3",
              actionButton("btn_remove", "Remove Column",
                           class = "btn-warning"))
      ),
      DTOutput("modified_table"),
      hidden(div(id = "msg_t3",
                 class = "alert alert-success mt-3",
                 "✅ Task 3 complete — 'Species' column removed!"))
    ),

    # ── Task 4: Histogram ──
    tabPanel(
      "4 · Histogram",
      br(),
      uiOutput("hint_t4"),
      h5("Create a Histogram"),
      div(class = "d-flex gap-2 align-items-end mb-3",
          div(selectInput("hist_col", "Select column:",
                          choices = NULL, width = "200px")),
          div(class = "mb-3",
              actionButton("btn_hist", "Create Histogram",
                           class = "btn-primary"))
      ),
      plotOutput("histogram_out", height = "350px"),
      hidden(div(id = "msg_t4",
                 class = "alert alert-success mt-3",
                 "✅ Task 4 complete — histogram created!"))
    ),

    # ── Task 5: Missing Values ──
    tabPanel(
      "5 · Missing Values",
      br(),
      uiOutput("hint_t5"),
      h5("Missing Value Report"),
      actionButton("btn_missing", "Check Missing Values",
                   class = "btn-primary mb-3"),
      DTOutput("missing_table"),
      hidden(div(id = "msg_t5",
                 class = "alert alert-success mt-3",
                 "✅ Task 5 complete — missing values identified!"))
    )
  )
)

# =============================================================================
# Server
# =============================================================================
server <- function(input, output, session) {

  # ── Reactive state ──────────────────────────────────────────────────────────
  rv <- reactiveValues(
    group        = as.character(ifelse(runif(1) > 0.5, "A", "B")),
    session_id   = paste0(sample(c(letters, 0:9), 8, replace = TRUE),
                          collapse = ""),
    started      = FALSE,
    start_time   = NULL,
    task_done    = rep(FALSE, N_TASKS),
    task_time_s  = rep(NA_real_,  N_TASKS), # seconds from start to completion
    current_data = task_data                # data that can be modified (Task 3)
  )

  # ── Generate fresh participant ID per session ────────────────────────────────
  updateTextInput(session, "pid",
                  value = paste0("P", sample(100:999, 1)))

  # ── Helper: mark a task done ────────────────────────────────────────────────
  next_tab_labels <- c("2 · Summary", "3 · Remove Column",
                       "4 · Histogram", "5 · Missing Values", NULL)

  complete_task <- function(i) {
    if (!rv$task_done[i] && rv$started) {
      rv$task_done[i]   <- TRUE
      rv$task_time_s[i] <- round(as.numeric(Sys.time()) - rv$start_time, 1)
      shinyjs::show(paste0("msg_t", i))
      # Version B: show notification to click next section
      if (isTRUE(rv$group == "B") && i < N_TASKS) {
        showNotification(
          ui       = tags$span("✅ Task complete! Please click ",
                               tags$strong(next_tab_labels[i]), " to continue."),
          type     = "message",
          duration = 6
        )
      } else if (isTRUE(rv$group == "B") && i == N_TASKS) {
        showNotification(
          ui       = tags$span("🎉 All tasks done! Please click ",
                               tags$strong("Submit & Finish"), " on the left to submit your results."),
          type     = "message",
          duration = 8
        )
      }
    }
  }

  # ── Control welcome vs. task sidebar ────────────────────────────────────────
  output$show_welcome <- reactive({
    if (rv$started) "no" else "yes"
  })
  outputOptions(output, "show_welcome", suspendWhenHidden = FALSE)

  # ── Start button ─────────────────────────────────────────────────────────────
  observeEvent(input$start_btn, {
    rv$started    <- TRUE
    rv$start_time <- as.numeric(Sys.time())
    updateTabsetPanel(session, "main_tabs", selected = "1 · View Data")
  })

  # ── Hint boxes (shown only in Version B) ────────────────────────────────────
  make_hint <- function(step, text) {
    renderUI({
      if (isTRUE(rv$group == "B")) {
        div(class = "alert alert-info d-flex gap-2 align-items-start mb-3",
            tags$span("💡", style = "font-size:1.2rem"),
            div(tags$strong(paste0("Step ", step, ": ")), text)
        )
      }
    })
  }

  output$hint_t1 <- make_hint(1, "The dataset is pre-loaded for you. Browsing the first few rows gives you a quick sense of the data structure — how many columns there are, what types of values they contain, and whether anything looks unusual. Scroll through the table below to complete this task.")
  output$hint_t2 <- make_hint(2, "Summary statistics (min, max, mean, median) help you understand the range and central tendency of each column — essential before doing any analysis. Click 'Generate Summary' to produce these statistics for all columns at once.")
  output$hint_t3 <- make_hint(3, "For numerical analysis, it's best to work with numeric columns only. 'Species' is the only categorical (text) column in this dataset, so it should be removed. Select 'Species' from the dropdown and click 'Remove Column'.")
  output$hint_t4 <- make_hint(4, "A histogram shows the distribution of a variable — whether it's symmetric, skewed, or has outliers. To find the variable with the highest mean, refer to the summary statistics from Task 2. Sepal.Length has the highest mean (~5.84). Select 'Sepal.Length' from the dropdown and click 'Create Histogram'.")
  output$hint_t5 <- make_hint(5, "Missing values can distort analysis results if not identified and handled. Checking which columns have missing data is a critical step in data quality assessment. Click 'Check Missing Values' to see a report of missing entries per column.")

  # ── Task 1: View Data ────────────────────────────────────────────────────────
  output$data_table <- renderDT({
    datatable(head(task_data, 10),
              options = list(pageLength = 10, dom = "t", scrollX = TRUE))
  })

  # Auto-complete Task 1 when the user navigates to the tab
  observeEvent(input$main_tabs, {
    if (input$main_tabs == "1 · View Data") complete_task(1)
  })

  # ── Task 2: Summary Stats ────────────────────────────────────────────────────
  observeEvent(input$btn_summary, {
    complete_task(2)
  })

  output$summary_out <- renderPrint({
    req(input$btn_summary)
    summary(task_data)
  })

  # ── Task 3: Remove Column ────────────────────────────────────────────────────
  # Populate column dropdowns from current data
  observe({
    cols     <- names(rv$current_data)
    num_cols <- cols[sapply(rv$current_data, is.numeric)]
    updateSelectInput(session, "col_to_remove", choices = cols)
    updateSelectInput(session, "hist_col",      choices = num_cols)
  })

  observeEvent(input$btn_remove, {
    req(input$col_to_remove)
    rv$current_data <- rv$current_data[,
      names(rv$current_data) != input$col_to_remove, drop = FALSE]
    # Credit for Task 3 specifically requires removing 'Species'
    if (input$col_to_remove == "Species") complete_task(3)
  })

  output$modified_table <- renderDT({
    datatable(head(rv$current_data, 10),
              options = list(dom = "t", scrollX = TRUE))
  })

  # ── Task 4: Histogram ────────────────────────────────────────────────────────
  observeEvent(input$btn_hist, {
    req(input$hist_col)
    # Credit for Task 4 specifically requires plotting 'Sepal.Length'
    if (input$hist_col == "Sepal.Length") complete_task(4)
  })

  output$histogram_out <- renderPlot({
    req(input$btn_hist, input$hist_col)
    col <- input$hist_col
    ggplot(task_data, aes(x = .data[[col]])) +
      geom_histogram(fill = "#3498db", colour = "white", bins = 20) +
      labs(title = paste("Histogram of", col), x = col, y = "Count") +
      theme_minimal(base_size = 14)
  })

  # ── Task 5: Missing Values ────────────────────────────────────────────────────
  observeEvent(input$btn_missing, {
    complete_task(5)
  })

  output$missing_table <- renderDT({
    req(input$btn_missing)
    miss_df <- data.frame(
      Column      = names(task_data),
      N_Missing   = sapply(task_data, function(x) sum(is.na(x))),
      Pct_Missing = round(sapply(task_data,
                                 function(x) mean(is.na(x))) * 100, 1),
      stringsAsFactors = FALSE
    )
    datatable(miss_df, options = list(dom = "t"))
  })

  # ── Task checklist sidebar ────────────────────────────────────────────────────
  output$task_checklist <- renderUI({
    tags$ul(
      class = "list-unstyled small",
      lapply(seq_len(N_TASKS), function(i) {
        done <- rv$task_done[i]
        tags$li(
          class = paste("py-1", if (done) "text-success fw-semibold" else "text-muted"),
          if (done) "✅ " else "⬜ ",
          TASK_LABELS[i]
        )
      })
    )
  })

  output$progress_bar_ui <- renderUI({
    n   <- sum(rv$task_done)
    pct <- round(n / N_TASKS * 100)
    div(
      tags$small(class = "text-muted",
                 paste0(n, " / ", N_TASKS, " tasks completed")),
      div(class = "progress mt-1", style = "height:8px",
          div(class = "progress-bar bg-success",
              role = "progressbar",
              style = paste0("width:", pct, "%"),
              `aria-valuenow` = pct,
              `aria-valuemin` = 0,
              `aria-valuemax` = 100))
    )
  })

  # ── Post-task questions (shown to all participants after starting) ───────────
  output$post_task_questions <- renderUI({
    if (rv$started) {
      div(
        class = "mb-3",
        tags$p(class = "fw-bold small mb-2", "📝 Two quick questions:"),
        tags$div(
          class = "small mb-3",
          tags$label("Do you have prior experience with data analysis or data processing?"),
          radioButtons("q_experience", label = NULL,
                       choices = c("Yes", "No"),
                       inline = TRUE)
        ),
        tags$div(
          class = "small mb-3",
          tags$label("Did you find the 5 tasks difficult to understand?"),
          radioButtons("q_difficulty", label = NULL,
                       choices = c("Yes", "No"),
                       inline = TRUE)
        ),
        hr()
      )
    }
  })

  # ── Submit to Google Sheets ───────────────────────────────────────────────────
  observeEvent(input$submit_btn, {
    elapsed <- if (!is.null(rv$start_time))
      round(as.numeric(Sys.time()) - rv$start_time)
    else NA

    payload <- list(
      session_id          = rv$session_id,
      participant_id      = input$pid,
      group               = rv$group,
      n_tasks_done        = sum(rv$task_done),
      total_time_sec      = elapsed,
      t1_done  = rv$task_done[1],  t1_time_s = rv$task_time_s[1],
      t2_done  = rv$task_done[2],  t2_time_s = rv$task_time_s[2],
      t3_done  = rv$task_done[3],  t3_time_s = rv$task_time_s[3],
      t4_done  = rv$task_done[4],  t4_time_s = rv$task_time_s[4],
      t5_done  = rv$task_done[5],  t5_time_s = rv$task_time_s[5],
      prior_experience    = if (!is.null(input$q_experience)) input$q_experience else NA,
      tasks_hard_to_understand = if (!is.null(input$q_difficulty)) input$q_difficulty else NA,
      timestamp           = format(Sys.time(), "%Y-%m-%d %H:%M:%S")
    )

    # Silent POST — failure does not affect participant experience
    tryCatch({
      httr::POST(
        SHEETS_URL,
        body   = jsonlite::toJSON(list(payload), auto_unbox = TRUE),
        encode = "raw",
        httr::content_type("application/json")
      )
    }, error = function(e) NULL)

    showModal(modalDialog(
      title = "✅ All done — thank you!",
      tags$p(paste0("You completed ", sum(rv$task_done),
                    " out of ", N_TASKS, " tasks.")),
      tags$p("Your results have been recorded. You may close this window."),
      easyClose = TRUE,
      footer    = modalButton("Close")
    ))
  })
}

# =============================================================================
# Launch
# =============================================================================
shinyApp(ui, server)
